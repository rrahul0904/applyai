from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.worker_runtime_models import WorkerRuntimeHeartbeat


@dataclass(frozen=True)
class WorkerHeartbeatStatus:
    healthy: bool
    worker_id: str | None
    heartbeat_at: datetime | None
    deployment_sha: str | None


def current_deployment_sha() -> str | None:
    for key in (
        "RAILWAY_GIT_COMMIT_SHA",
        "GITHUB_SHA",
        "GIT_SHA",
        "VERCEL_GIT_COMMIT_SHA",
    ):
        value = os.getenv(key, "").strip()
        if value:
            return value[:64]
    return None


def record_worker_heartbeat(
    *,
    environment: str,
    worker_type: str,
    worker_id: str,
    deployment_sha: str | None = None,
    now: datetime | None = None,
) -> None:
    """Persist or refresh one worker instance's liveness receipt."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        raise ValueError("worker heartbeat timestamp must be timezone-aware")
    values = {
        "environment": environment[:48],
        "worker_type": worker_type[:80],
        "worker_id": worker_id[:160],
        "deployment_sha": deployment_sha[:64] if deployment_sha else None,
        "heartbeat_at": moment,
    }
    statement = insert(WorkerRuntimeHeartbeat).values(**values)
    statement = statement.on_conflict_do_update(
        constraint="uq_worker_runtime_heartbeats_instance",
        set_={
            "heartbeat_at": statement.excluded.heartbeat_at,
            "deployment_sha": statement.excluded.deployment_sha,
        },
    )
    with SessionLocal.begin() as session:
        session.execute(statement)


def get_latest_worker_heartbeat(
    *,
    environment: str,
    worker_type: str,
    max_age_seconds: int,
    now: datetime | None = None,
) -> WorkerHeartbeatStatus:
    """Return the newest heartbeat for an exact environment/type and its freshness."""
    if max_age_seconds < 1:
        raise ValueError("max_age_seconds must be positive")
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        raise ValueError("worker heartbeat query timestamp must be timezone-aware")
    with SessionLocal() as session:
        row = session.scalar(
            select(WorkerRuntimeHeartbeat)
            .where(
                WorkerRuntimeHeartbeat.environment == environment,
                WorkerRuntimeHeartbeat.worker_type == worker_type,
            )
            .order_by(WorkerRuntimeHeartbeat.heartbeat_at.desc(), WorkerRuntimeHeartbeat.id)
            .limit(1)
        )
    if row is None:
        return WorkerHeartbeatStatus(False, None, None, None)
    heartbeat_at = row.heartbeat_at
    if heartbeat_at.tzinfo is None:
        heartbeat_at = heartbeat_at.replace(tzinfo=UTC)
    age = moment.astimezone(UTC) - heartbeat_at.astimezone(UTC)
    healthy = timedelta(0) <= age <= timedelta(seconds=max_age_seconds)
    return WorkerHeartbeatStatus(
        healthy=healthy,
        worker_id=row.worker_id,
        heartbeat_at=heartbeat_at,
        deployment_sha=row.deployment_sha,
    )
