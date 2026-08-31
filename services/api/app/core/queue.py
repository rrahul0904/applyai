import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock
from typing import Any

import boto3
from fastapi import Depends
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings


SOURCE_TASK_TYPES = {"SOURCE_DISCOVERY", "SOURCE_INGEST", "SOURCE_VERIFY"}
AI_TASK_TYPES = {
    "AI_DEEP_MATCH",
    "AI_RESUME_TAILOR",
    "AI_APPLICATION_COPILOT",
    "AI_INTERVIEW_PREP",
}
AGENT_TASK_TYPES = {"AGENT_RUN"}
SPECIAL_TASK_TYPES = SOURCE_TASK_TYPES | AI_TASK_TYPES | AGENT_TASK_TYPES


def sqs_client(*, region: str):
    endpoint_url = os.getenv("SQS_ENDPOINT_URL") or None
    return boto3.client("sqs", region_name=region, endpoint_url=endpoint_url)


def resolve_agent_queue_url(settings: Settings) -> str | None:
    if settings.agent_sqs_queue_url:
        return settings.agent_sqs_queue_url
    if settings.task_queue_provider != "sqs":
        return None
    if settings.app_env.lower() in {"staging", "production"}:
        queue_name = f"applyai-{settings.app_env.lower()}-agent-tasks"
        try:
            return sqs_client(region=settings.sqs_region).get_queue_url(QueueName=queue_name)["QueueUrl"]
        except Exception:
            return None
    return settings.sqs_queue_url


@dataclass(frozen=True)
class Task:
    task_type: str
    payload: dict[str, Any]
    idempotency_key: str


class TaskQueue(ABC):
    @abstractmethod
    def enqueue(self, task: Task) -> None:
        raise NotImplementedError


class InMemoryTaskQueue(TaskQueue):
    def __init__(self) -> None:
        self.tasks: list[Task] = []
        self.keys: set[str] = set()
        self.lock = Lock()

    def enqueue(self, task: Task) -> None:
        with self.lock:
            if task.idempotency_key in self.keys:
                return
            self.keys.add(task.idempotency_key)
            self.tasks.append(task)


class SqsTaskQueue(TaskQueue):
    def __init__(self, queue_url: str, region: str) -> None:
        self.queue_url = queue_url
        self.client = sqs_client(region=region)

    def enqueue(self, task: Task) -> None:
        kwargs: dict[str, Any] = {
            "QueueUrl": self.queue_url,
            "MessageBody": json.dumps(
                {
                    "task_type": task.task_type,
                    "payload": task.payload,
                    "idempotency_key": task.idempotency_key,
                }
            ),
            "MessageAttributes": {
                "task_type": {"DataType": "String", "StringValue": task.task_type},
                "idempotency_key": {"DataType": "String", "StringValue": task.idempotency_key},
            },
        }
        if self.queue_url.endswith(".fifo"):
            kwargs["MessageDeduplicationId"] = task.idempotency_key
            kwargs["MessageGroupId"] = task.task_type
        self.client.send_message(**kwargs)


class PostgresTaskQueue(TaskQueue):
    """Materialize outbox events into an idempotent PostgreSQL work queue.

    The outbox transaction remains the domain/event boundary. This queue owns only worker
    delivery state. A unique idempotency key makes an outbox publish retry safe if the task row
    was committed but the publisher crashed before marking its outbox event published.
    """

    def enqueue(self, task: Task) -> None:
        # Lazy imports avoid creating a queue <-> database module import cycle at process start.
        from app.core.database import SessionLocal
        from app.postgres_queue_models import PostgresTask

        with SessionLocal() as session:
            try:
                with session.begin_nested():
                    session.add(
                        PostgresTask(
                            task_type=task.task_type,
                            payload=task.payload,
                            idempotency_key=task.idempotency_key,
                            status="QUEUED",
                        )
                    )
                    session.flush()
                session.commit()
            except IntegrityError:
                session.rollback()
                # A task with the same key is already durable. Treat duplicate publication as
                # success so the corresponding outbox event can advance to PUBLISHED.
                return


_development_queue = InMemoryTaskQueue()
_source_development_queue = InMemoryTaskQueue()
_ai_development_queue = InMemoryTaskQueue()
_agent_development_queue = InMemoryTaskQueue()
_postgres_queue = PostgresTaskQueue()


def supports_task_type(settings: Settings, task_type: str) -> bool:
    if settings.task_queue_provider in {"memory", "postgres"}:
        return True
    if task_type in AGENT_TASK_TYPES:
        return bool(resolve_agent_queue_url(settings))
    if task_type in AI_TASK_TYPES:
        return bool(settings.ai_sqs_queue_url)
    if task_type in SOURCE_TASK_TYPES:
        return bool(settings.source_sqs_queue_url)
    return bool(settings.sqs_queue_url)


def get_task_queue_for_type(
    settings: Settings,
    *,
    task_type: str | None = None,
) -> TaskQueue:
    is_source_task = task_type in SOURCE_TASK_TYPES
    is_ai_task = task_type in AI_TASK_TYPES
    is_agent_task = task_type in AGENT_TASK_TYPES
    if settings.task_queue_provider == "postgres":
        return _postgres_queue
    if settings.task_queue_provider == "sqs":
        if is_agent_task:
            queue_url = resolve_agent_queue_url(settings)
            family = "agent"
        elif is_ai_task:
            queue_url = settings.ai_sqs_queue_url
            family = "AI"
        elif is_source_task:
            queue_url = settings.source_sqs_queue_url
            family = "source"
        else:
            queue_url = settings.sqs_queue_url
            family = "default"
        if not queue_url:
            raise RuntimeError(f"A dedicated {family} queue URL is required")
        return SqsTaskQueue(queue_url, settings.sqs_region)
    if is_agent_task:
        return _agent_development_queue
    if is_ai_task:
        return _ai_development_queue
    if is_source_task:
        return _source_development_queue
    return _development_queue


def get_task_queue(settings: Settings = Depends(get_settings)) -> TaskQueue:
    return get_task_queue_for_type(settings)
