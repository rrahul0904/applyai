from __future__ import annotations

import json
import logging
import socket
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.job_source_models import JobSourceRegistry
from app.jobs.contracts import SourceHealthStatus
from app.jobs.registry import sync_configured_sources


logger = logging.getLogger("applyai.source_dispatcher")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def dispatch_due_sources(
    settings: Settings | None = None,
    *,
    dispatcher_id: str | None = None,
) -> list[uuid.UUID]:
    """Atomically lease due sources and create durable SOURCE_INGEST outbox tasks."""
    settings = settings or get_settings()
    dispatcher_id = dispatcher_id or f"dispatcher:{socket.gethostname()}:{uuid.uuid4()}"
    with SessionLocal() as session:
        sync_configured_sources(session, settings)

    with SessionLocal() as session:
        now = utcnow()
        active_leases = session.scalar(
            select(func.count(JobSourceRegistry.id)).where(
                JobSourceRegistry.lease_expires_at.is_not(None),
                JobSourceRegistry.lease_expires_at >= now,
            )
        ) or 0
        capacity = max(0, settings.job_source_max_inflight - active_leases)
        batch_size = min(settings.job_source_dispatch_batch_size, capacity)
        if batch_size <= 0:
            logger.info(
                "source_dispatch_backpressure",
                extra={
                    "active_leases": active_leases,
                    "max_inflight": settings.job_source_max_inflight,
                },
            )
            return []

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
                    JobSourceRegistry.id,
                )
                .with_for_update(skip_locked=True)
                .limit(batch_size)
            )
        )
        lease_expires_at = now + timedelta(seconds=settings.job_source_lease_seconds)
        dispatched_ids: list[uuid.UUID] = []
        for source in rows:
            token = f"source:{source.id}:{uuid.uuid4()}"
            source.locked_at = now
            source.locked_by = token
            source.lease_expires_at = lease_expires_at
            source.last_dispatch_at = now
            dispatch_epoch = int(now.timestamp())
            add_task_outbox_event(
                session,
                task=Task(
                    task_type="SOURCE_INGEST",
                    payload={
                        "source_id": str(source.id),
                        "lease_token": token,
                        "dispatched_at": now.isoformat(),
                    },
                    idempotency_key=f"source-ingest:{source.id}:{dispatch_epoch}",
                ),
                aggregate_type="JOB_SOURCE_REGISTRY",
                aggregate_id=source.id,
            )
            dispatched_ids.append(source.id)
        session.commit()

    logger.info(
        "source_dispatch_completed",
        extra={
            "dispatcher_id": dispatcher_id,
            "dispatched": len(dispatched_ids),
            "active_before": active_leases,
        },
    )
    return dispatched_ids


def main() -> None:
    source_ids = dispatch_due_sources()
    print(json.dumps({"dispatched": [str(value) for value in source_ids]}, sort_keys=True))


if __name__ == "__main__":
    main()
