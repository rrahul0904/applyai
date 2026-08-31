from __future__ import annotations

import json
import logging
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.outbox import publish_outbox_once
from app.core.queue import AGENT_TASK_TYPES, AI_TASK_TYPES, SOURCE_TASK_TYPES, Task
from app.postgres_queue_models import PostgresTask


logger = logging.getLogger("applyai.postgres_worker")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def claim_task(settings: Settings, *, worker_id: str) -> uuid.UUID | None:
    now = utcnow()
    with SessionLocal() as session:
        row = session.scalar(
            select(PostgresTask)
            .where(
                or_(
                    and_(
                        PostgresTask.status.in_(["QUEUED", "RETRY_WAIT"]),
                        PostgresTask.available_at <= now,
                    ),
                    and_(
                        PostgresTask.status == "RUNNING",
                        PostgresTask.lease_expires_at.is_not(None),
                        PostgresTask.lease_expires_at < now,
                    ),
                )
            )
            .order_by(PostgresTask.available_at, PostgresTask.created_at, PostgresTask.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        row.status = "RUNNING"
        row.attempt_count += 1
        row.leased_at = now
        row.lease_owner = worker_id
        row.lease_expires_at = now + timedelta(seconds=settings.postgres_task_lease_seconds)
        row.last_error = None
        session.commit()
        return row.id


def extend_lease(task_id: uuid.UUID, *, worker_id: str, settings: Settings) -> bool:
    now = utcnow()
    with SessionLocal() as session:
        result = session.execute(
            update(PostgresTask)
            .where(
                PostgresTask.id == task_id,
                PostgresTask.status == "RUNNING",
                PostgresTask.lease_owner == worker_id,
            )
            .values(lease_expires_at=now + timedelta(seconds=settings.postgres_task_lease_seconds))
        )
        session.commit()
        return bool(result.rowcount)


def _heartbeat(
    task_id: uuid.UUID,
    *,
    worker_id: str,
    settings: Settings,
    stop: threading.Event,
) -> None:
    interval = max(10.0, settings.postgres_task_lease_seconds / 3)
    while not stop.wait(interval):
        try:
            if not extend_lease(task_id, worker_id=worker_id, settings=settings):
                logger.warning("postgres_worker_lease_lost", extra={"task_id": str(task_id)})
                return
        except Exception:
            logger.exception("postgres_worker_lease_extension_failed", extra={"task_id": str(task_id)})
            return


def _body(task: Task) -> str:
    return json.dumps(
        {
            "task_type": task.task_type,
            "payload": task.payload,
            "idempotency_key": task.idempotency_key,
        }
    )


def dispatch_task(task: Task, settings: Settings) -> bool:
    body = _body(task)
    if task.task_type in SOURCE_TASK_TYPES:
        from app.workers.source import process_message

        return process_message(body, settings)
    if task.task_type in AI_TASK_TYPES:
        from app.workers.ai import process_message

        return process_message(body, settings)
    if task.task_type in AGENT_TASK_TYPES:
        from app.workers.agent import process_message

        return process_message(body, settings)

    from app.workers.resume import process_message

    return process_message(body, settings)


def complete_task(task_id: uuid.UUID, *, worker_id: str) -> bool:
    now = utcnow()
    with SessionLocal() as session:
        result = session.execute(
            update(PostgresTask)
            .where(
                PostgresTask.id == task_id,
                PostgresTask.status == "RUNNING",
                PostgresTask.lease_owner == worker_id,
            )
            .values(
                status="COMPLETED",
                completed_at=now,
                lease_owner=None,
                leased_at=None,
                lease_expires_at=None,
                last_error=None,
            )
        )
        session.commit()
        return bool(result.rowcount)


def retry_or_dead_task(
    task_id: uuid.UUID,
    *,
    worker_id: str,
    settings: Settings,
    error_code: str,
) -> str | None:
    now = utcnow()
    with SessionLocal() as session:
        row = session.scalar(
            select(PostgresTask)
            .where(
                PostgresTask.id == task_id,
                PostgresTask.status == "RUNNING",
                PostgresTask.lease_owner == worker_id,
            )
            .with_for_update()
        )
        if row is None:
            return None
        row.last_error = error_code[:1000]
        row.lease_owner = None
        row.leased_at = None
        row.lease_expires_at = None
        if row.attempt_count >= settings.postgres_task_max_attempts:
            row.status = "DEAD"
        else:
            delay = min(
                settings.postgres_task_retry_base_seconds * (2 ** max(0, row.attempt_count - 1)),
                3600,
            )
            row.status = "RETRY_WAIT"
            row.available_at = now + timedelta(seconds=delay)
        session.commit()
        return row.status


def cancel_task(task_id: uuid.UUID) -> bool:
    now = utcnow()
    with SessionLocal() as session:
        result = session.execute(
            update(PostgresTask)
            .where(
                PostgresTask.id == task_id,
                PostgresTask.status.in_(["QUEUED", "RETRY_WAIT"]),
            )
            .values(
                status="CANCELLED",
                cancelled_at=now,
                lease_owner=None,
                leased_at=None,
                lease_expires_at=None,
            )
        )
        session.commit()
        return bool(result.rowcount)


def process_claimed_task(task_id: uuid.UUID, *, worker_id: str, settings: Settings) -> bool:
    with SessionLocal() as session:
        row = session.scalar(
            select(PostgresTask).where(
                PostgresTask.id == task_id,
                PostgresTask.status == "RUNNING",
                PostgresTask.lease_owner == worker_id,
            )
        )
        if row is None:
            return False
        task = Task(
            task_type=row.task_type,
            payload=dict(row.payload),
            idempotency_key=row.idempotency_key,
        )

    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat,
        kwargs={
            "task_id": task_id,
            "worker_id": worker_id,
            "settings": settings,
            "stop": stop,
        },
        daemon=True,
    )
    heartbeat.start()
    acknowledged = False
    error_code = "PROCESSOR_RETRY"
    try:
        acknowledged = dispatch_task(task, settings)
    except Exception as exc:
        error_code = type(exc).__name__
        logger.exception(
            "postgres_worker_task_failed",
            extra={"task_id": str(task_id), "task_type": task.task_type},
        )
    finally:
        stop.set()
        heartbeat.join(timeout=1)

    if acknowledged:
        return complete_task(task_id, worker_id=worker_id)
    status = retry_or_dead_task(
        task_id,
        worker_id=worker_id,
        settings=settings,
        error_code=error_code,
    )
    logger.warning(
        "postgres_worker_task_not_acknowledged",
        extra={"task_id": str(task_id), "task_type": task.task_type, "next_status": status},
    )
    return False


def run_once(settings: Settings, *, worker_id: str) -> bool:
    # Publish committed domain events before claiming work. `PostgresTaskQueue` is idempotent,
    # so a crash between materialization and outbox acknowledgement is safe to replay.
    publish_outbox_once(settings, lock_owner=f"{worker_id}:outbox")
    task_id = claim_task(settings, worker_id=worker_id)
    if task_id is None:
        return False
    process_claimed_task(task_id, worker_id=worker_id, settings=settings)
    return True


def run_worker(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.task_queue_provider != "postgres":
        raise RuntimeError("PostgreSQL worker requires TASK_QUEUE_PROVIDER=postgres")
    worker_id = f"{socket.gethostname()}:{uuid.uuid4()}"
    logger.info("postgres_worker_started", extra={"worker_id": worker_id})
    while True:
        worked = run_once(settings, worker_id=worker_id)
        if not worked:
            time.sleep(settings.postgres_worker_poll_seconds)


if __name__ == "__main__":
    run_worker()
