from __future__ import annotations

import json
import logging
import threading
import uuid

from app.ai.runtime import execute_ai_run
from app.core.config import Settings, get_settings
from app.core.queue import sqs_client


logger = logging.getLogger("applyai.ai_worker")


def process_message(body: str, settings: Settings) -> bool:
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("ai_worker_invalid_json")
        return False
    task_type = message.get("task_type")
    if not isinstance(task_type, str) or not task_type.startswith("AI_"):
        logger.warning("ai_worker_unsupported_task", extra={"task_type": task_type})
        return True
    run_value = (message.get("payload") or {}).get("run_id")
    try:
        run_id = uuid.UUID(str(run_value))
    except (TypeError, ValueError):
        logger.warning("ai_worker_invalid_run_id")
        return False
    return execute_ai_run(run_id, settings)


def _visibility_heartbeat(*, client, queue_url: str, receipt_handle: str, settings: Settings, stop: threading.Event) -> None:
    while not stop.wait(settings.ai_sqs_visibility_heartbeat_seconds):
        try:
            client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=settings.ai_sqs_visibility_timeout_seconds,
            )
            logger.info("ai_worker_visibility_extended")
        except Exception:
            logger.exception("ai_worker_visibility_extension_failed")
            return


def run_worker(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    queue_url = settings.ai_sqs_queue_url or settings.sqs_queue_url
    if settings.task_queue_provider != "sqs" or not queue_url:
        raise RuntimeError("AI worker requires TASK_QUEUE_PROVIDER=sqs and an AI/default queue URL")
    client = sqs_client(region=settings.sqs_region)
    logger.info("ai_worker_started", extra={"visibility_timeout": settings.ai_sqs_visibility_timeout_seconds})
    while True:
        response = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=settings.sqs_wait_time_seconds,
            VisibilityTimeout=settings.ai_sqs_visibility_timeout_seconds,
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in response.get("Messages", []):
            receipt_handle = message["ReceiptHandle"]
            stop = threading.Event()
            heartbeat = threading.Thread(
                target=_visibility_heartbeat,
                kwargs={
                    "client": client,
                    "queue_url": queue_url,
                    "receipt_handle": receipt_handle,
                    "settings": settings,
                    "stop": stop,
                },
                daemon=True,
            )
            heartbeat.start()
            acknowledged = False
            try:
                acknowledged = process_message(message.get("Body", ""), settings)
            except Exception:
                logger.exception("ai_worker_unexpected_failure")
            finally:
                stop.set()
                heartbeat.join(timeout=1)
            if acknowledged:
                client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


if __name__ == "__main__":
    run_worker()
