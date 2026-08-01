from __future__ import annotations

import logging
import socket
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.job_source_models import JobSourceRegistry
from app.jobs.adapters import JobSourceAdapterFactory
from app.jobs.contracts import JobSourceType, SourceHealthStatus, SourceTrustLevel
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline


logger = logging.getLogger("applyai.job_source_registry")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_TRUST_PRIORITY = {
    SourceTrustLevel.EMPLOYER_DIRECT.value: 100,
    SourceTrustLevel.OFFICIAL_ATS.value: 90,
    SourceTrustLevel.EMPLOYER_CAREER_SITE.value: 80,
    SourceTrustLevel.LICENSED_FEED.value: 70,
    SourceTrustLevel.STRUCTURED_JOB_PAGE.value: 60,
    SourceTrustLevel.THIRD_PARTY_SOURCE.value: 40,
    SourceTrustLevel.UNVERIFIED.value: 20,
}


def upsert_source(
    session: Session,
    *,
    source_type: JobSourceType,
    source_name: str,
    source_identity: str,
    base_url: str | None,
    configuration: dict,
    interval_seconds: int,
    trust_level: SourceTrustLevel = SourceTrustLevel.OFFICIAL_ATS,
) -> JobSourceRegistry:
    source = session.scalar(
        select(JobSourceRegistry).where(
            JobSourceRegistry.source_type == source_type.value,
            JobSourceRegistry.source_identity == source_identity,
        )
    )
    if source is None:
        source = JobSourceRegistry(
            source_type=source_type.value,
            source_name=source_name,
            source_identity=source_identity,
            base_url=base_url,
            configuration=configuration,
            trust_level=trust_level.value,
            priority=_TRUST_PRIORITY[trust_level.value],
            enabled=True,
            crawl_allowed=True,
            health_status=SourceHealthStatus.HEALTHY.value,
            crawl_interval_seconds=interval_seconds,
            min_interval_seconds=min(900, interval_seconds),
            max_interval_seconds=max(604_800, interval_seconds),
            next_run_at=utcnow(),
        )
        session.add(source)
        session.flush()
        return source

    source.source_name = source_name
    source.base_url = base_url
    source.configuration = configuration
    source.trust_level = trust_level.value
    source.priority = max(source.priority or 0, _TRUST_PRIORITY[trust_level.value])
    source.crawl_interval_seconds = interval_seconds
    return source


def sync_configured_sources(
    session: Session,
    settings: Settings | None = None,
) -> list[JobSourceRegistry]:
    settings = settings or get_settings()
    sources: list[JobSourceRegistry] = []
    for board_token in settings.greenhouse_board_tokens:
        token = board_token.strip()
        if not token:
            continue
        sources.append(
            upsert_source(
                session,
                source_type=JobSourceType.GREENHOUSE,
                source_name=f"Greenhouse: {token}",
                source_identity=token,
                base_url=f"https://boards.greenhouse.io/{token}",
                configuration={"board_token": token},
                interval_seconds=settings.job_source_default_interval_seconds,
            )
        )
    for site in settings.lever_site_names:
        site_name = site.strip()
        if not site_name:
            continue
        sources.append(
            upsert_source(
                session,
                source_type=JobSourceType.LEVER,
                source_name=f"Lever: {site_name}",
                source_identity=site_name,
                base_url=f"https://jobs.lever.co/{site_name}",
                configuration={
                    "site": site_name,
                    "region": "global",
                    "max_pages": settings.job_source_max_pages,
                },
                interval_seconds=settings.job_source_default_interval_seconds,
            )
        )
    for board_name in settings.ashby_board_names:
        name = board_name.strip()
        if not name:
            continue
        sources.append(
            upsert_source(
                session,
                source_type=JobSourceType.ASHBY,
                source_name=f"Ashby: {name}",
                source_identity=name,
                base_url=f"https://jobs.ashbyhq.com/{name}",
                configuration={"board_name": name, "include_compensation": True},
                interval_seconds=settings.job_source_default_interval_seconds,
            )
        )
    session.commit()
    return sources


def claim_due_source_ids(
    session: Session,
    *,
    settings: Settings,
    worker_id: str,
) -> list[uuid.UUID]:
    now = utcnow()
    rows = list(
        session.scalars(
            select(JobSourceRegistry)
            .where(
                JobSourceRegistry.enabled.is_(True),
                JobSourceRegistry.crawl_allowed.is_(True),
                JobSourceRegistry.next_run_at <= now,
                JobSourceRegistry.health_status.notin_(
                    [SourceHealthStatus.DISABLED.value, SourceHealthStatus.BLOCKED.value]
                ),
                or_(
                    JobSourceRegistry.lease_expires_at.is_(None),
                    JobSourceRegistry.lease_expires_at < now,
                ),
            )
            .order_by(
                JobSourceRegistry.priority.desc(),
                JobSourceRegistry.next_run_at,
                JobSourceRegistry.created_at,
            )
            .with_for_update(skip_locked=True)
            .limit(settings.job_source_claim_batch_size)
        )
    )
    lease_expires_at = now + timedelta(seconds=settings.job_source_lease_seconds)
    for source in rows:
        source.locked_at = now
        source.locked_by = worker_id
        source.lease_expires_at = lease_expires_at
    session.commit()
    return [source.id for source in rows]


def adaptive_interval_seconds(source: JobSourceRegistry, settings: Settings) -> int:
    minimum = max(settings.job_source_min_interval_seconds, source.min_interval_seconds)
    maximum = min(settings.job_source_max_interval_seconds, source.max_interval_seconds)
    base = max(minimum, min(source.crawl_interval_seconds, maximum))

    if source.consecutive_failures > 0:
        failure_interval = base * (2 ** min(source.consecutive_failures, 8))
        return min(
            maximum,
            settings.job_source_failure_max_backoff_seconds,
            failure_interval,
        )

    changes = max(0, source.last_change_count)
    volume = max(0, source.last_job_count)
    if changes >= 25 or (volume >= 100 and changes / max(volume, 1) >= 0.10):
        return max(minimum, int(base * 0.5))
    if changes > 0 or volume >= 1_000:
        return max(minimum, int(base * 0.75))
    if volume == 0:
        return min(maximum, int(base * 2.0))
    return min(maximum, int(base * 1.25))


def run_registered_source(
    source_id: uuid.UUID,
    *,
    settings: Settings | None = None,
    expected_worker_id: str | None = None,
) -> dict[str, int]:
    settings = settings or get_settings()
    with SessionLocal() as session:
        source = session.get(JobSourceRegistry, source_id)
        if source is None:
            raise LookupError(f"Job source {source_id} does not exist")
        if expected_worker_id and source.locked_by != expected_worker_id:
            raise RuntimeError("Job source lease is not owned by this worker")
        if not source.enabled or not source.crawl_allowed:
            raise RuntimeError("Job source is disabled or crawling is not allowed")

        connector = JobSourceAdapterFactory.create(source)
        counts: dict[str, int] | None = None
        try:
            health = connector.health()
            if not health.healthy:
                raise RuntimeError(health.detail)
            counts = RegisteredSourceIngestionPipeline(session).run(source, connector)
            source = session.get(JobSourceRegistry, source_id)
            if source is not None:
                source.last_change_count = counts["created"] + counts["updated"] + counts["closed"]
            return counts
        finally:
            close = getattr(connector, "close", None)
            if callable(close):
                close()
            source = session.get(JobSourceRegistry, source_id)
            if source is not None:
                source.next_run_at = utcnow() + timedelta(
                    seconds=adaptive_interval_seconds(source, settings)
                )
                source.locked_at = None
                source.locked_by = None
                source.lease_expires_at = None
                session.commit()


def run_due_sources(settings: Settings | None = None) -> dict[str, dict[str, int] | str]:
    """Compatibility synchronous runner retained for local operations/tests.

    Staging Prompt 3 uses the transactional dispatcher and dedicated source queue.
    """
    settings = settings or get_settings()
    worker_id = f"{socket.gethostname()}:{uuid.uuid4()}"
    with SessionLocal() as session:
        sync_configured_sources(session, settings)
        source_ids = claim_due_source_ids(
            session,
            settings=settings,
            worker_id=worker_id,
        )

    results: dict[str, dict[str, int] | str] = {}
    for source_id in source_ids:
        try:
            results[str(source_id)] = run_registered_source(
                source_id,
                settings=settings,
                expected_worker_id=worker_id,
            )
        except Exception as exc:
            logger.exception(
                "job_source_run_failed",
                extra={"source_id": str(source_id), "worker_id": worker_id},
            )
            results[str(source_id)] = type(exc).__name__
            with SessionLocal() as session:
                source = session.get(JobSourceRegistry, source_id)
                if source is not None:
                    source.next_run_at = utcnow() + timedelta(
                        seconds=adaptive_interval_seconds(source, settings)
                    )
                    source.locked_at = None
                    source.locked_by = None
                    source.lease_expires_at = None
                    session.commit()
    return results
