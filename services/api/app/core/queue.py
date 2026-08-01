import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock
from typing import Any

import boto3
from fastapi import Depends

from app.core.config import Settings, get_settings


SOURCE_TASK_TYPES = {"SOURCE_DISCOVERY", "SOURCE_INGEST", "SOURCE_VERIFY"}


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
                "idempotency_key": {"DataType": "String", "StringValue": task.idempotency_key},
            },
        }
        if self.queue_url.endswith(".fifo"):
            kwargs["MessageDeduplicationId"] = task.idempotency_key
            kwargs["MessageGroupId"] = task.task_type
        self.client.send_message(**kwargs)


_development_queue = InMemoryTaskQueue()
_source_development_queue = InMemoryTaskQueue()


def get_task_queue_for_type(
    settings: Settings,
    *,
    task_type: str | None = None,
) -> TaskQueue:
    """Resolve a queue for a server-owned task type.

    This function is intentionally not a FastAPI dependency. Keeping task_type out of
    dependency signatures prevents internal worker-routing details from becoming public
    request parameters in OpenAPI.
    """
    is_source_task = task_type in SOURCE_TASK_TYPES
    if settings.task_queue_provider == "sqs":
        queue_url = (
            settings.source_sqs_queue_url
            if is_source_task and settings.source_sqs_queue_url
            else settings.sqs_queue_url
        )
        if not queue_url:
            raise RuntimeError("A queue URL is required for the SQS task provider")
        return SqsTaskQueue(queue_url, settings.sqs_region)
    return _source_development_queue if is_source_task else _development_queue


def get_task_queue(settings: Settings = Depends(get_settings)) -> TaskQueue:
    """FastAPI dependency for the default candidate task queue."""
    return get_task_queue_for_type(settings)
