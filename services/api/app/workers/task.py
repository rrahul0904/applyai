from __future__ import annotations

import json
import logging
import threading

import boto3

from app.core.config import Settings, get_settings
from app.workers.discovery import process_message as process_discovery_message
from app.workers.resume import process_message as process_resume_message


logger = logging.getLogger("applyai.task_worker")


def process_message(body: str, settings: Settings) -> bool:
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("task_worker_invalid_json")
        return False
    task_type = message.get("task_type")
    if task_type == "RESUME_PARSE":
        return process_resume_message(body, settings)
    if task_type in {"JOB_URL_IMPORT", "SOURCE_DISCOVERY"}:
        return process_discovery_message(body, settings)
    logger.warning("task_worker_unsupported_task", extra={"task_type": task_type})
    # Unknown task types are acknowledged so one malformed producer cannot poison
    # this queue indefinitely. Supported domain tasks remain idempotent/retryable.
    return True


def _visibility_heartbeat(
    *,
    client,
    queue_url: str,
    receipt_handle: str,
    settings: Settings,
    stop: threading.Event,
) -> None:
    while not stop.wait(settings.sqs_visibility_heartbeat_seconds):
        try:
            client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=settings.sqs_visibility_timeout_seconds,
            )
            logger.info("task_worker_visibility_extended")
        except Exception:
            logger.exception("task_worker_visibility_extension_failed")
            return


def run_worker(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.task_queue_provider != "sqs" or not settings.sqs_queue_url:
        raise RuntimeError("Task worker requires TASK_QUEUE_PROVIDER=sqs and SQS_QUEUE_URL")

    client = boto3.client("sqs", region_name=settings.sqs_region)
    logger.info(
        "task_worker_started",
        extra={"visibility_timeout": settings.sqs_visibility_timeout_seconds},
    )
    while True:
        response = client.receive_message(
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=settings.sqs_wait_time_seconds,
            VisibilityTimeout=settings.sqs_visibility_timeout_seconds,
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in response.get("Messages", []):
            receipt_handle = message["ReceiptHandle"]
            acknowledged = False
            heartbeat_stop = threading.Event()
            heartbeat = threading.Thread(
                target=_visibility_heartbeat,
                kwargs={
                    "client": client,
                    "queue_url": settings.sqs_queue_url,
                    "receipt_handle": receipt_handle,
                    "settings": settings,
                    "stop": heartbeat_stop,
                },
                daemon=True,
            )
            heartbeat.start()
            try:
                acknowledged = process_message(message.get("Body", ""), settings)
            except Exception:
                logger.exception("task_worker_unexpected_failure")
            finally:
                heartbeat_stop.set()
                heartbeat.join(timeout=1)

            if acknowledged:
                client.delete_message(
                    QueueUrl=settings.sqs_queue_url,
                    ReceiptHandle=receipt_handle,
                )


if __name__ == "__main__":
    run_worker()
