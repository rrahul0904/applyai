from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.job_quality_models import JobApplyUrlCheck, JobClosureEvidence
from app.jobs.pipeline import JobIngestionPipeline
from app.jobs.web_security import CrawlBudget, SafeHttpFetcher
from app.models import Job, JobSource, JobSourceLink, JobStatusHistory


logger = logging.getLogger("applyai.job_verifier")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _status_for(http_status: int, redirected: bool) -> str:
    if 200 <= http_status < 300:
        return "REDIRECTED" if redirected else "VALID"
    if http_status in {404, 410}:
        return "NOT_FOUND"
    if http_status in {401, 403, 429}:
        return "FORBIDDEN"
    return "ERROR"


def _evidence_key(source_id: uuid.UUID, http_status: int) -> str:
    return hashlib.sha256(f"{source_id}:{http_status}".encode()).hexdigest()[:32]


def verify_job_source_url(
    job_source_id: uuid.UUID,
    *,
    settings: Settings | None = None,
    fetcher: SafeHttpFetcher | None = None,
) -> JobApplyUrlCheck:
    settings = settings or get_settings()
    own_fetcher = fetcher is None
    fetcher = fetcher or SafeHttpFetcher(
        budget=CrawlBudget(
            max_pages=2,
            max_response_bytes=128 * 1024,
            max_redirects=settings.career_discovery_max_redirects,
            request_timeout_seconds=settings.career_discovery_timeout_seconds,
        ),
        user_agent="ApplyAI-ApplyUrlVerifier/1.0",
    )
    started = time.monotonic()
    try:
        with SessionLocal() as session:
            source = session.get(JobSource, job_source_id)
            if source is None:
                raise LookupError(f"Job source {job_source_id} does not exist")
            requested_url = source.source_url
            try:
                result = fetcher.fetch(
                    requested_url,
                    accept="text/html,application/xhtml+xml,*/*;q=0.1",
                )
                redirected = result.final_url != result.requested_url
                status = _status_for(result.status_code, redirected)
                error_category = None
                resolved_url = result.final_url
                http_status = result.status_code
            except Exception as exc:
                status = "ERROR"
                error_category = type(exc).__name__
                resolved_url = None
                http_status = None

            interval = (
                settings.apply_url_valid_interval_seconds
                if status in {"VALID", "REDIRECTED"}
                else settings.apply_url_error_interval_seconds
            )
            check = JobApplyUrlCheck(
                job_source_id=source.id,
                url=requested_url,
                status=status,
                http_status=http_status,
                resolved_url=resolved_url,
                response_ms=int((time.monotonic() - started) * 1000),
                error_category=error_category,
                checked_at=utcnow(),
                next_check_at=utcnow() + timedelta(seconds=interval),
            )
            session.add(check)

            link = session.scalar(
                select(JobSourceLink).where(JobSourceLink.job_source_id == source.id)
            )
            if link is not None:
                job = session.get(Job, link.job_id)
                if job is not None:
                    _apply_closure_evidence(session, settings, job, source, check)
            session.commit()
            session.refresh(check)
            logger.info(
                "apply_url_verified",
                extra={
                    "job_source_id": str(source.id),
                    "status": status,
                    "http_status": http_status,
                    "response_ms": check.response_ms,
                },
            )
            return check
    finally:
        if own_fetcher:
            fetcher.close()


def _apply_closure_evidence(
    session: Session,
    settings: Settings,
    job: Job,
    source: JobSource,
    check: JobApplyUrlCheck,
) -> None:
    checkpoint = dict(source.checkpoint or {})
    if check.status in {"VALID", "REDIRECTED"}:
        checkpoint["confirmed_closed"] = False
        checkpoint["apply_url_not_found_count"] = 0
        checkpoint["last_apply_url_status"] = check.status
        source.checkpoint = checkpoint
        if job.status in {"UNKNOWN", "STALE", "CLOSED"}:
            previous = job.status
            job.status = "ACTIVE"
            job.closed_at = None
            session.add(
                JobStatusHistory(
                    job_id=job.id,
                    from_status=previous,
                    to_status="ACTIVE",
                    reason="APPLY_URL_VALID_AGAIN",
                )
            )
        return

    if check.status != "NOT_FOUND" or check.http_status is None:
        checkpoint["last_apply_url_status"] = check.status
        source.checkpoint = checkpoint
        return

    count = int(checkpoint.get("apply_url_not_found_count") or 0) + 1
    checkpoint["apply_url_not_found_count"] = count
    checkpoint["last_apply_url_status"] = check.status
    strength = "STRONG" if check.http_status == 410 else "MODERATE"
    evidence = JobClosureEvidence(
        job_id=job.id,
        job_source_id=source.id,
        evidence_type=f"HTTP_{check.http_status}",
        evidence_key=_evidence_key(source.id, check.http_status),
        strength=strength,
        detail={"confirmation_count": count, "url": source.source_url},
        applied=False,
    )
    existing = session.scalar(
        select(JobClosureEvidence).where(
            JobClosureEvidence.job_id == job.id,
            JobClosureEvidence.job_source_id == source.id,
            JobClosureEvidence.evidence_type == evidence.evidence_type,
            JobClosureEvidence.evidence_key == evidence.evidence_key,
        )
    )
    if existing is None:
        session.add(evidence)
    else:
        existing.detail = {"confirmation_count": count, "url": source.source_url}
        existing.observed_at = utcnow()
        evidence = existing

    if count >= settings.apply_url_not_found_confirmations:
        checkpoint["confirmed_closed"] = True
        evidence.applied = True
    source.checkpoint = checkpoint

    target = JobIngestionPipeline(session).canonical_status_from_sources(job.id, job.status)
    if target != job.status:
        previous = job.status
        job.status = target
        if target == "CLOSED":
            job.closed_at = utcnow()
        session.add(
            JobStatusHistory(
                job_id=job.id,
                from_status=previous,
                to_status=target,
                reason="APPLY_URL_CLOSURE_EVIDENCE",
            )
        )


def due_job_source_ids(session: Session, *, settings: Settings) -> list[uuid.UUID]:
    latest = (
        select(
            JobApplyUrlCheck.job_source_id,
            func.max(JobApplyUrlCheck.checked_at).label("checked_at"),
        )
        .group_by(JobApplyUrlCheck.job_source_id)
        .subquery()
    )
    latest_checks = (
        select(JobApplyUrlCheck.job_source_id, JobApplyUrlCheck.next_check_at)
        .join(
            latest,
            (latest.c.job_source_id == JobApplyUrlCheck.job_source_id)
            & (latest.c.checked_at == JobApplyUrlCheck.checked_at),
        )
        .subquery()
    )
    now = utcnow()
    return list(
        session.scalars(
            select(JobSource.id)
            .outerjoin(latest_checks, latest_checks.c.job_source_id == JobSource.id)
            .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
            .join(Job, Job.id == JobSourceLink.job_id)
            .where(
                Job.status.in_(["ACTIVE", "UNKNOWN", "STALE"]),
                (latest_checks.c.next_check_at.is_(None))
                | (latest_checks.c.next_check_at <= now),
            )
            .order_by(Job.last_seen_at.desc(), JobSource.id)
            .limit(settings.apply_url_check_batch_size)
        )
    )
