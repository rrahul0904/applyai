import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.core.queue import sqs_client


@dataclass(frozen=True)
class FailedTaskSummary:
    message_id: str | None
    task_type: str | None
    idempotency_key: str | None
    resume_version_id: str | None
    approximate_receive_count: int | None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def summarize_message(message: dict[str, Any]) -> FailedTaskSummary:
    """Return operational identifiers only; never expose resume content or raw bodies."""
    task_type: str | None = None
    idempotency_key: str | None = None
    resume_version_id: str | None = None

    try:
        body = json.loads(message.get("Body", ""))
    except (TypeError, json.JSONDecodeError):
        body = {}

    if isinstance(body, dict):
        raw_task_type = body.get("task_type")
        raw_idempotency_key = body.get("idempotency_key")
        payload = body.get("payload")
        if isinstance(raw_task_type, str):
            task_type = raw_task_type
        if isinstance(raw_idempotency_key, str):
            idempotency_key = raw_idempotency_key
        if isinstance(payload, dict) and payload.get("resume_version_id") is not None:
            resume_version_id = str(payload["resume_version_id"])

    attributes = message.get("Attributes") or {}
    return FailedTaskSummary(
        message_id=message.get("MessageId"),
        task_type=task_type,
        idempotency_key=idempotency_key,
        resume_version_id=resume_version_id,
        approximate_receive_count=_safe_int(attributes.get("ApproximateReceiveCount")),
    )


def inspect_resume_dlq(*, settings: Settings | None = None, limit: int = 10, client: Any | None = None) -> list[FailedTaskSummary]:
    settings = settings or get_settings()
    if settings.task_queue_provider != "sqs":
        raise RuntimeError("DLQ inspection requires TASK_QUEUE_PROVIDER=sqs")
    if not settings.sqs_dlq_url:
        raise RuntimeError("DLQ inspection requires SQS_DLQ_URL")
    if limit < 1 or limit > 10:
        raise ValueError("limit must be between 1 and 10")

    sqs = client or sqs_client(region=settings.sqs_region)
    response = sqs.receive_message(
        QueueUrl=settings.sqs_dlq_url,
        MaxNumberOfMessages=limit,
        WaitTimeSeconds=0,
        VisibilityTimeout=0,
        AttributeNames=["ApproximateReceiveCount"],
    )
    return [summarize_message(message) for message in response.get("Messages", [])]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect failed resume task identifiers in the configured SQS DLQ.")
    parser.add_argument("--limit", type=int, default=10, choices=range(1, 11))
    args = parser.parse_args()
    summaries = inspect_resume_dlq(limit=args.limit)
    print(json.dumps([asdict(summary) for summary in summaries], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
