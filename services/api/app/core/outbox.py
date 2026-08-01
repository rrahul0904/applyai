import logging
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.queue import Task, TaskQueue, get_task_queue_for_type
from app.durability_models import TaskOutbox


logger = logging.getLogger("applyai.task_outbox")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_task_outbox_event(
    session: Session,
    *,
    task: Task,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
) -> TaskOutbox:
    event = TaskOutbox(
        event_type=task.task_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=task.payload,
        idempotency_key=task.idempotency_key,
        status="PENDING",
    )
    session.add(event)
    return event


def claim_outbox_batch(
    session: Session,
    *,
    settings: Settings,
    lock_owner: str,
) -> list[uuid.UUID]:
    now = utcnow()
    stale_lock = now - timedelta(seconds=settings.outbox_lock_timeout_seconds)
    rows = list(
        session.scalars(
            select(TaskOutbox)
            .where(
                TaskOutbox.published_at.is_(None),
                TaskOutbox.available_at <= now,
                or_(
                    TaskOutbox.status == "PENDING",
                    (TaskOutbox.status == "CLAIMED") & (TaskOutbox.locked_at < stale_lock),
                ),
            )
            .order_by(TaskOutbox.created_at, TaskOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(settings.outbox_batch_size)
        )
    )
    for row in rows:
        row.status = "CLAIMED"
        row.locked_at = now
        row.lock_owner = lock_owner
    session.commit()
    return [row.id for row in rows]


def publish_claimed_event(
    event_id: uuid.UUID,
    *,
    queue: TaskQueue | None,
    settings: Settings,
    lock_owner: str,
) -> bool:
    with SessionLocal() as session:
        event = session.scalar(
            select(TaskOutbox).where(
                TaskOutbox.id == event_id,
                TaskOutbox.status == "CLAIMED",
                TaskOutbox.lock_owner == lock_owner,
                TaskOutbox.published_at.is_(None),
            )
        )
        if event is None:
            return True

        target_queue = queue or get_task_queue_for_type(settings, task_type=event.event_type)
        try:
            target_queue.enqueue(
                Task(
                    task_type=event.event_type,
                    payload=event.payload,
                    idempotency_key=event.idempotency_key,
                )
            )
        except Exception as exc:
            event.attempt_count += 1
            delay = min(
                settings.outbox_retry_base_seconds * (2 ** max(0, event.attempt_count - 1)),
                3600,
            )
            event.status = "PENDING"
            event.available_at = utcnow() + timedelta(seconds=delay)
            event.locked_at = None
            event.lock_owner = None
            event.last_error = type(exc).__name__
            session.commit()
            logger.warning(
                "task_outbox_publish_failed",
                extra={"outbox_id": str(event.id), "event_type": event.event_type},
            )
            return False

        event.status = "PUBLISHED"
        event.published_at = utcnow()
        event.locked_at = None
        event.lock_owner = None
        event.last_error = None
        session.commit()
        logger.info(
            "task_outbox_published",
            extra={"outbox_id": str(event.id), "event_type": event.event_type},
        )
        return True


def publish_outbox_once(
    settings: Settings | None = None,
    *,
    queue: TaskQueue | None = None,
    lock_owner: str | None = None,
) -> int:
    settings = settings or get_settings()
    lock_owner = lock_owner or f"{socket.gethostname()}:{uuid.uuid4()}"
    with SessionLocal() as session:
        event_ids = claim_outbox_batch(session, settings=settings, lock_owner=lock_owner)
    for event_id in event_ids:
        publish_claimed_event(
            event_id,
            queue=queue,
            settings=settings,
            lock_owner=lock_owner,
        )
    return len(event_ids)


def run_outbox_publisher(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    lock_owner = f"{socket.gethostname()}:{uuid.uuid4()}"
    logger.info("task_outbox_publisher_started", extra={"lock_owner": lock_owner})
    while True:
        published = publish_outbox_once(settings, lock_owner=lock_owner)
        if published == 0:
            time.sleep(1)


if __name__ == "__main__":
    run_outbox_publisher()
