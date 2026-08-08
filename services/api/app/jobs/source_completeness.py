from __future__ import annotations

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
        # Generic career pages and bounded partner feeds are intentionally conservative.
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


def closure_authoritative(value: SourceCompleteness | str) -> bool:
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
    configuration: dict[str, Any] = dict(source.configuration or {})
    configuration["last_source_completeness"] = completeness.value
    configuration["last_source_completeness_at"] = datetime.now(timezone.utc).isoformat()
    if counts is not None:
        configuration["last_source_completeness_counts"] = {
            key: int(counts.get(key, 0))
            for key in ("fetched", "valid", "invalid", "failed", "created", "updated", "closed")
        }
    source.configuration = configuration
    return completeness
