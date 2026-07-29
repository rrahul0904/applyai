from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock
from typing import Any

import boto3
from fastapi import Depends

from app.core.config import Settings, get_settings


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
        import json

        self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(
                {
                    "task_type": task.task_type,
                    "payload": task.payload,
                    "idempotency_key": task.idempotency_key,
                }
            ),
            MessageDeduplicationId=task.idempotency_key,
            MessageGroupId=task.task_type,
        )


_development_queue = InMemoryTaskQueue()


def get_task_queue(settings: Settings = Depends(get_settings)) -> TaskQueue:
    del settings
    return _development_queue
