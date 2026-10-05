from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import JobSourceConnector


class SourceCompleteness(StrEnum):
    FULL_SNAPSHOT = "FULL_SNAPSHOT"
    PAGINATED_FULL_SNAPSHOT = "PAGINATED_FULL_SNAPSHOT"
    DELTA = "DELTA"
    PARTIAL = "PARTIAL"
    TRUNCATED = "TRUNCATED"
    UNKNOWN_COMPLETENESS = "UNKNOWN_COMPLETENESS"


class CoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SourceCoverageReceipt:
    status: CoverageStatus
    observed_record_count: int
    pagination_complete: bool | None
    partitions_expected: int | None
    partitions_observed: int | None
    completeness_checks: tuple[tuple[str, bool | None], ...]
    last_successful_full_snapshot_at: str | None
    reason_codes: tuple[str, ...]
    legacy_completeness: SourceCompleteness

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "observed_record_count": self.observed_record_count,
            "pagination_complete": self.pagination_complete,
            "partitions_expected": self.partitions_expected,
            "partitions_observed": self.partitions_observed,
            "completeness_checks": {
                key: value for key, value in self.completeness_checks
            },
            "last_successful_full_snapshot_at": self.last_successful_full_snapshot_at,
            "reason_codes": list(self.reason_codes),
            "legacy_completeness": self.legacy_completeness.value,
        }


FULL_COMPLETENESS = {
    SourceCompleteness.FULL_SNAPSHOT,
    SourceCompleteness.PAGINATED_FULL_SNAPSHOT,
}

PAGINATED_FULL_CONNECTORS = {
    "lever",
    "ashby",
    "smartrecruiters",
    "usajobs",
    "reliefweb",
}

FULL_CONNECTORS = {
    "greenhouse",
    "development-seed",
}


def connector_completeness(connector: JobSourceConnector) -> SourceCompleteness:
    explicit = getattr(connector, "source_completeness", None)
    if explicit:
        try:
            return SourceCompleteness(str(explicit))
        except ValueError:
            return SourceCompleteness.UNKNOWN_COMPLETENESS

    authoritative = getattr(connector, "authoritative_snapshot", None)
    key = str(getattr(connector, "key", "")).casefold()
    if authoritative is False:
        return SourceCompleteness.PARTIAL
    if authoritative is True:
        return (
            SourceCompleteness.PAGINATED_FULL_SNAPSHOT
            if key in PAGINATED_FULL_CONNECTORS
            else SourceCompleteness.FULL_SNAPSHOT
        )
    if key in PAGINATED_FULL_CONNECTORS:
        return SourceCompleteness.PAGINATED_FULL_SNAPSHOT
    if key in FULL_CONNECTORS:
        return SourceCompleteness.FULL_SNAPSHOT
    return SourceCompleteness.UNKNOWN_COMPLETENESS


def observed_completeness(
    connector: JobSourceConnector,
    counts: dict[str, int] | None,
) -> SourceCompleteness:
    expected = connector_completeness(connector)
    if counts is None:
        return SourceCompleteness.UNKNOWN_COMPLETENESS
    if int(counts.get("failed", 0)) > 0:
        return SourceCompleteness.PARTIAL
    return expected


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coverage_checks(connector: JobSourceConnector) -> tuple[tuple[str, bool | None], ...]:
    raw = getattr(connector, "completeness_checks", None)
    if callable(raw):
        raw = raw()
    if not isinstance(raw, dict):
        return ()
    normalized: list[tuple[str, bool | None]] = []
    for key, value in sorted(raw.items()):
        normalized.append((str(key), value if isinstance(value, bool) else None))
    return tuple(normalized)


def observed_coverage(
    connector: JobSourceConnector,
    counts: dict[str, int] | None,
    previous_configuration: dict[str, Any] | None = None,
) -> SourceCoverageReceipt:
    legacy = observed_completeness(connector, counts)
    previous = previous_configuration or {}
    last_full = previous.get("last_successful_full_snapshot_at")
    observed = int((counts or {}).get("fetched", 0))
    pagination_complete = getattr(connector, "pagination_complete", None)
    if not isinstance(pagination_complete, bool):
        pagination_complete = None
    expected_partitions = _optional_int(
        getattr(connector, "coverage_partitions_expected", None)
    )
    observed_partitions = _optional_int(
        getattr(connector, "coverage_partitions_observed", None)
    )
    checks = _coverage_checks(connector)
    reasons: list[str] = []

    explicit = getattr(connector, "coverage_status", None)
    status: CoverageStatus | None = None
    if explicit is not None:
        try:
            status = CoverageStatus(str(explicit))
        except ValueError:
            reasons.append("INVALID_EXPLICIT_COVERAGE_STATUS")

    if counts is None:
        status = CoverageStatus.INCONCLUSIVE
        reasons.append("NO_COUNT_RECEIPT")
    elif int(counts.get("failed", 0)) > 0:
        status = CoverageStatus.PARTIAL
        reasons.append("RECORD_PROCESSING_FAILURES")
    elif status is None:
        if legacy in FULL_COMPLETENESS:
            status = CoverageStatus.COMPLETE
        elif legacy in {SourceCompleteness.PARTIAL, SourceCompleteness.TRUNCATED}:
            status = CoverageStatus.PARTIAL
            reasons.append("LEGACY_PARTIAL_OR_TRUNCATED")
        else:
            status = CoverageStatus.INCONCLUSIVE
            reasons.append("SOURCE_COMPLETENESS_NOT_PROVEN")

    if pagination_complete is False and status is not CoverageStatus.FAILED:
        status = CoverageStatus.PARTIAL
        reasons.append("PAGINATION_INCOMPLETE")

    if expected_partitions is not None:
        if observed_partitions is None:
            if status is CoverageStatus.COMPLETE:
                status = CoverageStatus.INCONCLUSIVE
            reasons.append("PARTITION_COVERAGE_UNKNOWN")
        elif observed_partitions < expected_partitions:
            status = CoverageStatus.PARTIAL
            reasons.append("PARTITIONS_MISSING")

    if any(value is False for _, value in checks):
        status = CoverageStatus.PARTIAL
        reasons.append("COMPLETENESS_CHECK_FAILED")
    elif checks and any(value is None for _, value in checks):
        if status is CoverageStatus.COMPLETE:
            status = CoverageStatus.INCONCLUSIVE
        reasons.append("COMPLETENESS_CHECK_INCONCLUSIVE")

    assert status is not None
    return SourceCoverageReceipt(
        status=status,
        observed_record_count=observed,
        pagination_complete=pagination_complete,
        partitions_expected=expected_partitions,
        partitions_observed=observed_partitions,
        completeness_checks=checks,
        last_successful_full_snapshot_at=str(last_full) if last_full else None,
        reason_codes=tuple(dict.fromkeys(reasons)),
        legacy_completeness=legacy,
    )


def failed_coverage_receipt(
    previous_configuration: dict[str, Any] | None = None,
    *,
    reason: str,
) -> SourceCoverageReceipt:
    previous = previous_configuration or {}
    return SourceCoverageReceipt(
        status=CoverageStatus.FAILED,
        observed_record_count=0,
        pagination_complete=None,
        partitions_expected=None,
        partitions_observed=None,
        completeness_checks=(),
        last_successful_full_snapshot_at=(
            str(previous["last_successful_full_snapshot_at"])
            if previous.get("last_successful_full_snapshot_at")
            else None
        ),
        reason_codes=(reason,),
        legacy_completeness=SourceCompleteness.UNKNOWN_COMPLETENESS,
    )


def closure_authoritative(
    value: SourceCompleteness | CoverageStatus | SourceCoverageReceipt | str,
) -> bool:
    if isinstance(value, SourceCoverageReceipt):
        return value.status is CoverageStatus.COMPLETE
    try:
        if CoverageStatus(str(value)) is CoverageStatus.COMPLETE:
            return True
    except ValueError:
        pass
    try:
        completeness = SourceCompleteness(str(value))
    except ValueError:
        return False
    return completeness in FULL_COMPLETENESS


def record_source_completeness(
    source: JobSourceRegistry,
    connector: JobSourceConnector,
    counts: dict[str, int] | None,
) -> SourceCompleteness:
    completeness = observed_completeness(connector, counts)
    coverage = observed_coverage(connector, counts, source.configuration)
    configuration: dict[str, Any] = dict(source.configuration or {})
    now = datetime.now(timezone.utc).isoformat()
    configuration["last_source_completeness"] = completeness.value
    configuration["last_source_completeness_at"] = now
    coverage_details = coverage.as_dict()
    if coverage.status is CoverageStatus.COMPLETE:
        configuration["last_successful_full_snapshot_at"] = now
        coverage_details["last_successful_full_snapshot_at"] = now
    configuration["last_source_coverage"] = coverage_details
    if counts is not None:
        configuration["last_source_completeness_counts"] = {
            key: int(counts.get(key, 0))
            for key in ("fetched", "valid", "invalid", "failed", "created", "updated", "closed")
        }
    source.configuration = configuration
    return completeness
