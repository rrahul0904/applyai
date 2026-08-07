import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock
from typing import Any

import boto3
from fastapi import Depends

from app.core.config import Settings, get_settings


SOURCE_TASK_TYPES = {"SOURCE_DISCOVERY", "SOURCE_INGEST", "SOURCE_VERIFY"}
AI_TASK_TYPES = {
    "AI_DEEP_MATCH",
    "AI_RESUME_TAILOR",
    "AI_APPLICATION_COPILOT",
    "AI_INTERVIEW_PREP",
}
SPECIAL_TASK_TYPES = SOURCE_TASK_TYPES | AI_TASK_TYPES


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
        self.client = boto3.client("sqs", region_name=region)

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
                "idempotency_key": {
                    "DataType": "String",
                    "StringValue": task.idempotency_key,
                },
            },
        }
        if self.queue_url.endswith(".fifo"):
            kwargs["MessageDeduplicationId"] = task.idempotency_key
            kwargs["MessageGroupId"] = task.task_type
        self.client.send_message(**kwargs)


_development_queue = InMemoryTaskQueue()
_source_development_queue = InMemoryTaskQueue()
_ai_development_queue = InMemoryTaskQueue()


def supports_task_type(settings: Settings, task_type: str) -> bool:
    if settings.task_queue_provider != "sqs":
        return True
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
    """Resolve a queue for a server-owned task type.

    Dedicated source and AI task families fail closed when their queue is absent. This
    prevents an incorrectly configured publisher from routing specialized work onto the
    resume/default queue.
    """
    is_source_task = task_type in SOURCE_TASK_TYPES
    is_ai_task = task_type in AI_TASK_TYPES
    if settings.task_queue_provider == "sqs":
        if is_ai_task:
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
    if is_ai_task:
        return _ai_development_queue
    if is_source_task:
        return _source_development_queue
    return _development_queue


def get_task_queue(settings: Settings = Depends(get_settings)) -> TaskQueue:
    """FastAPI dependency for the default candidate task queue."""
    return get_task_queue_for_type(settings)
