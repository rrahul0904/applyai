import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.outbox import publish_outbox_once
from app.core.queue import Task, TaskQueue
from app.durability_models import TaskOutbox


class RecordingQueue(TaskQueue):
    def __init__(self) -> None:
        self.tasks: list[Task] = []

    def enqueue(self, task: Task) -> None:
        self.tasks.append(task)


def test_published_outbox_event_is_not_published_twice(database_url):
    aggregate_id = uuid.uuid4()
    engine = create_engine(database_url)
    with Session(engine) as session:
        event = TaskOutbox(
            event_type="RESUME_PARSE",
            aggregate_type="RESUME_VERSION",
            aggregate_id=aggregate_id,
            payload={"resume_version_id": str(aggregate_id)},
            idempotency_key=f"resume-parse:{aggregate_id}",
            status="PENDING",
        )
        session.add(event)
        session.commit()
        event_id = event.id
    engine.dispose()

    queue = RecordingQueue()
    settings = Settings()
    assert publish_outbox_once(settings, queue=queue, lock_owner="publisher-a") == 1
    assert publish_outbox_once(settings, queue=queue, lock_owner="publisher-b") == 0
    assert len(queue.tasks) == 1
    assert queue.tasks[0].idempotency_key == f"resume-parse:{aggregate_id}"

    engine = create_engine(database_url)
    with Session(engine) as session:
        event = session.get(TaskOutbox, event_id)
        assert event is not None
        assert event.status == "PUBLISHED"
        assert event.published_at is not None
        assert event.attempt_count == 0
    engine.dispose()


def test_outbox_idempotency_key_is_unique(database_url):
    aggregate_id = uuid.uuid4()
    engine = create_engine(database_url)
    with Session(engine) as session:
        session.add(
            TaskOutbox(
                event_type="RESUME_PARSE",
                aggregate_type="RESUME_VERSION",
                aggregate_id=aggregate_id,
                payload={},
                idempotency_key="same-task",
                status="PENDING",
            )
        )
        session.commit()
        first_id = session.scalar(
            select(TaskOutbox.id).where(TaskOutbox.idempotency_key == "same-task")
        )
        assert first_id is not None

        session.add(
            TaskOutbox(
                event_type="RESUME_PARSE",
                aggregate_type="RESUME_VERSION",
                aggregate_id=uuid.uuid4(),
                payload={},
                idempotency_key="same-task",
                status="PENDING",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    engine.dispose()
