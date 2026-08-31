from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.durability_models import JobIngestionRun
from app.job_source_models import JobSourceRegistry
from app.jobs.adapters import raw_from_connector
from app.jobs.connectors import JobSourceConnector, NormalizedJob
from app.jobs.contracts import (
    SourceHealthStatus,
    ValidationStatus,
    canonicalize_public_url,
    classify_ingestion_error,
    normalize_title,
    validate_raw_job,
)
from app.jobs.pipeline import JobIngestionPipeline, normalize_text, payload_hash
from app.jobs.source_authority import record_field_provenance, should_source_update_canonical
from app.jobs.source_completeness import closure_authoritative, observed_completeness
from app.models import (
    Job,
    JobLocation,
    JobSource,
    JobSourceLink,
    JobStatusHistory,
    RawJobPosting as RawJobPostingModel,
)


logger = logging.getLogger("applyai.job_source_pipeline")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthorityAwareJobIngestionPipeline(JobIngestionPipeline):
    """Preserve all source links while allowing only the selected source to mutate canonical fields."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._active_connector: str | None = None
        self._active_external_job_id: str | None = None

    def ingest_one(
        self,
        connector_key: str,
        item: NormalizedJob,
        *,
        source_company: str | None = None,
    ) -> str:
        self._active_connector = connector_key
        self._active_external_job_id = item.external_job_id
        try:
            return super().ingest_one(
                connector_key,
                item,
                source_company=source_company,
            )
        finally:
            self._active_connector = None
            self._active_external_job_id = None

    def canonical_changed(self, job: Job, item: NormalizedJob) -> bool:
        if not super().canonical_changed(job, item):
            return False
        if not self._active_connector or not self._active_external_job_id:
            return True
        posting_source = self.session.scalar(
            select(JobSource).where(
                JobSource.connector_key == self._active_connector,
                JobSource.external_job_id == self._active_external_job_id,
            )
        )
        if posting_source is None:
            return True
        return should_source_update_canonical(
            self.session,
            job.id,
            posting_source.id,
        )

    def find_dedup_candidate(
        self,
        *,
        connector_key: str,
        company,
        item: NormalizedJob,
    ):
        candidate, reason, confidence = super().find_dedup_candidate(
            connector_key=connector_key,
            company=company,
            item=item,
        )
        if candidate is not None:
            return candidate, reason, confidence

        canonical_apply_url = canonicalize_public_url(item.application_url)
        if canonical_apply_url:
            link = self.session.scalar(
                select(JobSourceLink)
                .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
                .where(JobSource.checkpoint["canonical_apply_url"].astext == canonical_apply_url)
                .limit(1)
            )
            if link is not None:
                return self.session.get(Job, link.job_id), "CANONICAL_APPLICATION_URL", Decimal("1.0000")

        internal_job_id = item.raw_payload.get("_applyai_internal_job_id")
        if internal_job_id:
            link = self.session.scalar(
                select(JobSourceLink)
                .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
                .join(Job, Job.id == JobSourceLink.job_id)
                .where(
                    Job.company_id == company.id,
                    JobSource.checkpoint["internal_job_id"].astext == str(internal_job_id),
                )
                .limit(1)
            )
            if link is not None:
                return self.session.get(Job, link.job_id), "COMPANY_REQUISITION_ID", Decimal("1.0000")

        primary_location = item.locations[0] if item.locations else "Location not specified"
        candidates = list(
            self.session.scalars(
                select(Job)
                .join(JobLocation, JobLocation.job_id == Job.id)
                .where(
                    Job.company_id == company.id,
                    JobLocation.location_text == primary_location,
                    Job.status.in_(["ACTIVE", "UNKNOWN", "STALE"]),
                )
                .limit(50)
            ).unique()
        )
        target_title = normalize_title(item.title)
        target_description = normalize_text(item.description)
        for existing in candidates:
            if normalize_title(existing.title) != target_title:
                continue
            ratio = SequenceMatcher(
                None,
                normalize_text(existing.description)[:20_000],
                target_description[:20_000],
                autojunk=False,
            ).ratio()
            if ratio >= 0.94:
                return existing, "CROSS_SOURCE_DESCRIPTION_SIMILARITY", Decimal(str(round(ratio, 4)))
        return None, None, None


class RegisteredSourceIngestionPipeline:
    """Run one registry source while reusing the proven canonical job pipeline."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.canonical = AuthorityAwareJobIngestionPipeline(session)

    def run(
        self,
        source: JobSourceRegistry,
        connector: JobSourceConnector,
    ) -> dict[str, int]:
        started_monotonic = time.monotonic()
        now = utcnow()
        source.last_attempt_at = now
        run = JobIngestionRun(
            source_id=source.id,
            source_type=source.source_type,
            connector=connector.key,
            source_company=source.source_identity,
            status="RUNNING",
        )
        self.session.add(run)
        self.session.commit()
        logger.info(
            "job_ingestion_started",
            extra={
                "source_id": str(source.id),
                "run_id": str(run.id),
                "source_type": source.source_type,
            },
        )

        counts = {
            "fetched": 0,
            "valid": 0,
            "invalid": 0,
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "deduplicated": 0,
            "failed": 0,
            "stale": 0,
            "closed": 0,
        }
        try:
            payloads = connector.fetch(None)
        except Exception as exc:
            self._record_source_failure(source, run, exc, started_monotonic)
            raise

        seen_external_ids: set[str] = set()
        for payload in payloads:
            counts["fetched"] += 1
            try:
                raw = raw_from_connector(connector, payload)
                seen_external_ids.add(raw.external_job_id)
                validation = validate_raw_job(raw)
                if not validation.accepted:
                    counts["invalid"] += 1
                    with self.session.begin_nested():
                        self._persist_rejected_raw(source, connector, raw, validation)
                    continue

                counts["valid"] += 1
                normalized = connector.normalize(payload)
                source_company_identity = raw.source_company_identity or source.source_identity
                normalized.raw_payload.update(
                    {
                        "_applyai_source_registry_id": str(source.id),
                        "_applyai_source_type": source.source_type,
                        "_applyai_source_company_identity": source_company_identity,
                        "_applyai_source_job_identity": raw.source_job_identity,
                        "_applyai_source_url": raw.source_url,
                        "_applyai_canonical_apply_url": canonicalize_public_url(raw.apply_url),
                        "_applyai_internal_job_id": raw.internal_job_id,
                        "_applyai_validation_status": validation.status.value,
                        "_applyai_validation_warnings": list(validation.warnings),
                        "_applyai_source_metadata": raw.source_metadata,
                    }
                )
                with self.session.begin_nested():
                    result = self.canonical.ingest_one(
                        connector.key,
                        normalized,
                        source_company=source_company_identity,
                    )
                    posting_source = self.session.scalar(
                        select(JobSource).where(
                            JobSource.connector_key == connector.key,
                            JobSource.external_job_id == normalized.external_job_id,
                        )
                    )
                    if posting_source is None:
                        raise RuntimeError("Canonical ingestion did not create posting provenance")
                    checkpoint = dict(posting_source.checkpoint or {})
                    checkpoint.update(
                        {
                            "source_registry_id": str(source.id),
                            "source_type": source.source_type,
                            "source_company_identity": source_company_identity,
                            "source_job_identity": raw.source_job_identity,
                            "source_url": raw.source_url,
                            "canonical_apply_url": canonicalize_public_url(raw.apply_url),
                            "internal_job_id": raw.internal_job_id,
                            "validation_status": validation.status.value,
                            "validation_warnings": list(validation.warnings),
                            "source_metadata": raw.source_metadata,
                            "last_verified_at": utcnow().isoformat(),
                        }
                    )
                    posting_source.checkpoint = checkpoint
                    link = self.session.scalar(
                        select(JobSourceLink).where(
                            JobSourceLink.job_source_id == posting_source.id
                        )
                    )
                    if link is not None:
                        record_field_provenance(self.session, link.job_id)
                    dedup_reason = str(checkpoint.get("dedup_reason") or "")
                    if dedup_reason and dedup_reason not in {
                        "SOURCE_IDENTITY",
                        "NEW_CANONICAL_JOB",
                    }:
                        counts["deduplicated"] += 1
                counts[result] += 1
            except Exception:
                counts["failed"] += 1
                logger.exception(
                    "job_ingestion_record_failed",
                    extra={
                        "source_id": str(source.id),
                        "run_id": str(run.id),
                        "source_type": source.source_type,
                    },
                )

        completeness = observed_completeness(connector, counts)
        if counts["failed"] == 0:
            if closure_authoritative(completeness):
                freshness = self._apply_registry_freshness(source, seen_external_ids)
                counts["stale"] += freshness["stale"]
                counts["closed"] += freshness["closed"]
            else:
                logger.info(
                    "job_ingestion_non_authoritative_snapshot_freshness_skipped",
                    extra={
                        "source_id": str(source.id),
                        "fetched": counts["fetched"],
                        "source_completeness": completeness.value,
                    },
                )
            run.status = "COMPLETED"
            source.health_status = SourceHealthStatus.HEALTHY.value
            source.consecutive_failures = 0
            source.last_success_at = utcnow()
            source.last_failure_at = None
            source.last_error_category = None
            source.last_error_summary = None
        else:
            run.status = "PARTIAL"
            source.health_status = SourceHealthStatus.DEGRADED.value
            source.consecutive_failures += 1
            source.last_failure_at = utcnow()
            source.last_error_category = "PARSER_ERROR"
            source.last_error_summary = f"{counts['failed']} posting(s) failed"

        source.last_job_count = counts["valid"]
        configuration = dict(source.configuration or {})
        configuration["last_source_completeness"] = completeness.value
        configuration["last_source_completeness_at"] = utcnow().isoformat()
        source.configuration = configuration
        self._finish_run(run, counts, started_monotonic)
        self.session.commit()
        logger.info(
            "job_ingestion_completed" if run.status == "COMPLETED" else "job_ingestion_partial",
            extra={
                "source_id": str(source.id),
                "run_id": str(run.id),
                "source_type": source.source_type,
                "source_completeness": completeness.value,
                "duration_ms": run.duration_ms,
                "counts": counts,
            },
        )
        return counts

    def _persist_rejected_raw(self, source, connector, raw, validation) -> None:
        posting_source = self.session.scalar(
            select(JobSource).where(
                JobSource.connector_key == connector.key,
                JobSource.external_job_id == raw.external_job_id,
            )
        )
        checkpoint = {
            "source_registry_id": str(source.id),
            "source_type": source.source_type,
            "source_company_identity": raw.source_company_identity or source.source_identity,
            "source_job_identity": raw.source_job_identity,
            "source_url": raw.source_url,
            "canonical_apply_url": canonicalize_public_url(raw.apply_url),
            "validation_status": validation.status.value,
            "validation_errors": list(validation.errors),
            "validation_warnings": list(validation.warnings),
            "miss_count": 0,
        }
        if posting_source is None:
            posting_source = JobSource(
                connector_key=connector.key,
                external_job_id=raw.external_job_id,
                source_url=raw.apply_url or raw.source_url,
                checkpoint=checkpoint,
            )
            self.session.add(posting_source)
            self.session.flush()
        else:
            posting_source.checkpoint = checkpoint
            posting_source.last_seen_at = utcnow()

        content_hash = payload_hash(raw.raw_payload)
        existing = self.session.scalar(
            select(RawJobPostingModel).where(
                RawJobPostingModel.job_source_id == posting_source.id,
                RawJobPostingModel.content_hash == content_hash,
            )
        )
        if existing is None:
            self.session.add(
                RawJobPostingModel(
                    job_source_id=posting_source.id,
                    payload=raw.raw_payload,
                    content_hash=content_hash,
                    normalization_status=ValidationStatus.INVALID.value,
                )
            )

    def _apply_registry_freshness(
        self,
        source: JobSourceRegistry,
        seen_external_ids: set[str],
    ) -> dict[str, int]:
        counts = {"stale": 0, "closed": 0}
        posting_sources = list(
            self.session.scalars(
                select(JobSource).where(
                    JobSource.checkpoint["source_registry_id"].astext == str(source.id)
                )
            )
        )
        affected_job_ids: set[uuid.UUID] = set()
        for posting_source in posting_sources:
            if posting_source.external_job_id in seen_external_ids:
                continue
            checkpoint = dict(posting_source.checkpoint or {})
            checkpoint["miss_count"] = int(checkpoint.get("miss_count") or 0) + 1
            posting_source.checkpoint = checkpoint
            link = self.session.scalar(
                select(JobSourceLink).where(
                    JobSourceLink.job_source_id == posting_source.id
                )
            )
            if link is not None:
                affected_job_ids.add(link.job_id)

        for job_id in affected_job_ids:
            job = self.session.get(Job, job_id)
            if job is None:
                continue
            target_status = self.canonical.canonical_status_from_sources(job.id, job.status)
            if target_status == job.status:
                continue
            previous = job.status
            job.status = target_status
            if target_status == "CLOSED":
                job.closed_at = utcnow()
                counts["closed"] += 1
            elif target_status == "STALE":
                counts["stale"] += 1
            else:
                job.closed_at = None
            self.session.add(
                JobStatusHistory(
                    job_id=job.id,
                    from_status=previous,
                    to_status=target_status,
                    reason="SOURCE_REGISTRY_FRESHNESS_EVALUATED",
                )
            )
        return counts

    def _record_source_failure(
        self,
        source: JobSourceRegistry,
        run: JobIngestionRun,
        exc: Exception,
        started_monotonic: float,
    ) -> None:
        category = classify_ingestion_error(exc)
        source.consecutive_failures += 1
        source.last_failure_at = utcnow()
        source.last_error_category = category.value
        source.last_error_summary = type(exc).__name__
        source.health_status = (
            SourceHealthStatus.FAILING.value
            if source.consecutive_failures >= 3
            else SourceHealthStatus.DEGRADED.value
        )
        run.status = "FAILED"
        run.failed = 1
        run.error_category = category.value
        run.error_summary = type(exc).__name__
        run.completed_at = utcnow()
        run.duration_ms = int((time.monotonic() - started_monotonic) * 1000)
        self.session.commit()
        logger.warning(
            "job_ingestion_failed",
            extra={
                "source_id": str(source.id),
                "run_id": str(run.id),
                "source_type": source.source_type,
                "error_category": category.value,
            },
        )

    @staticmethod
    def _finish_run(
        run: JobIngestionRun,
        counts: dict[str, int],
        started_monotonic: float,
    ) -> None:
        run.fetched = counts["fetched"]
        run.valid = counts["valid"]
        run.invalid = counts["invalid"]
        run.created = counts["created"]
        run.updated = counts["updated"]
        run.unchanged = counts["unchanged"]
        run.deduplicated = counts["deduplicated"]
        run.failed = counts["failed"]
        run.stale = counts["stale"]
        run.closed = counts["closed"]
        run.completed_at = utcnow()
        run.duration_ms = int((time.monotonic() - started_monotonic) * 1000)