import json
import logging
import uuid

import boto3

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.storage import get_object_storage
from app.models import ResumeVersion
from app.resumes.processor import process_resume_version


logger = logging.getLogger("applyai.resume_worker")


def process_message(body: str, settings: Settings) -> bool:
    """Process one queue body.

    Returns True when the message can be acknowledged. Parser failures return False so
    SQS can retry and ultimately move the message to the queue's configured DLQ.
    """
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("resume_worker_invalid_json")
        return False

    if message.get("task_type") != "RESUME_PARSE":
        logger.warning("resume_worker_unsupported_task", extra={"task_type": message.get("task_type")})
        # Unknown tasks do not belong on this worker queue. Acknowledge them so they do
        # not create an infinite retry loop.
        return True

    resume_version_value = (message.get("payload") or {}).get("resume_version_id")
    try:
        resume_version_id = uuid.UUID(str(resume_version_value))
    except (TypeError, ValueError):
        logger.warning("resume_worker_invalid_resume_version_id")
        return False

    storage = get_object_storage(settings)
    process_resume_version(resume_version_id, storage)

    with SessionLocal() as session:
        version = session.get(ResumeVersion, resume_version_id)
        if version is None:
            logger.warning(
                "resume_worker_missing_version",
                extra={"resume_version_id": str(resume_version_id)},
            )
            return True
        if version.processing_status == "FAILED":
            logger.warning(
                "resume_worker_processing_failed",
                extra={"resume_version_id": str(resume_version_id)},
            )
            return False
    return True


def run_worker(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.task_queue_provider != "sqs" or not settings.sqs_queue_url:
        raise RuntimeError("Resume worker requires TASK_QUEUE_PROVIDER=sqs and SQS_QUEUE_URL")

    client = boto3.client("sqs", region_name=settings.sqs_region)
    logger.info("resume_worker_started")
    while True:
        response = client.receive_message(
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=120,
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in response.get("Messages", []):
            receipt_handle = message["ReceiptHandle"]
            acknowledged = False
            try:
                acknowledged = process_message(message.get("Body", ""), settings)
            except Exception:
                logger.exception("resume_worker_unexpected_failure")

            if acknowledged:
                client.delete_message(
                    QueueUrl=settings.sqs_queue_url,
                    ReceiptHandle=receipt_handle,
                )


if __name__ == "__main__":
    run_worker()
