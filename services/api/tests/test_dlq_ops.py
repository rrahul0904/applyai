import json

import pytest

from app.core.config import Settings
from app.ops.dlq import inspect_resume_dlq, summarize_message


class FakeSqsClient:
    def __init__(self, messages):
        self.messages = messages
        self.calls = []

    def receive_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"Messages": self.messages}


def sqs_settings(**overrides):
    values = {
        "task_queue_provider": "sqs",
        "sqs_queue_url": "https://sqs.us-east-1.amazonaws.com/123/main",
        "sqs_dlq_url": "https://sqs.us-east-1.amazonaws.com/123/dlq",
    }
    values.update(overrides)
    return Settings(**values)


def test_summarize_message_exposes_only_operational_identifiers():
    body = {
        "task_type": "RESUME_PARSE",
        "idempotency_key": "resume:version-1:parse",
        "payload": {
            "resume_version_id": "11111111-1111-1111-1111-111111111111",
            "resume_text": "must never be returned",
            "candidate_email": "candidate@example.test",
        },
    }
    summary = summarize_message(
        {
            "MessageId": "message-1",
            "Body": json.dumps(body),
            "Attributes": {"ApproximateReceiveCount": "5"},
        }
    )

    assert summary.message_id == "message-1"
    assert summary.task_type == "RESUME_PARSE"
    assert summary.idempotency_key == "resume:version-1:parse"
    assert summary.resume_version_id == "11111111-1111-1111-1111-111111111111"
    assert summary.approximate_receive_count == 5
    assert "resume_text" not in summary.__dict__
    assert "candidate_email" not in summary.__dict__


def test_inspect_resume_dlq_peeks_without_deleting_messages():
    fake = FakeSqsClient(
        [
            {
                "MessageId": "message-1",
                "Body": json.dumps(
                    {
                        "task_type": "RESUME_PARSE",
                        "idempotency_key": "resume:version-1:parse",
                        "payload": {"resume_version_id": "version-1"},
                    }
                ),
                "Attributes": {"ApproximateReceiveCount": "7"},
            }
        ]
    )

    summaries = inspect_resume_dlq(settings=sqs_settings(), limit=3, client=fake)

    assert len(summaries) == 1
    assert fake.calls == [
        {
            "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/dlq",
            "MaxNumberOfMessages": 3,
            "WaitTimeSeconds": 0,
            "VisibilityTimeout": 0,
            "AttributeNames": ["ApproximateReceiveCount"],
        }
    ]


def test_inspect_resume_dlq_requires_explicit_dlq_url():
    with pytest.raises(RuntimeError, match="SQS_DLQ_URL"):
        inspect_resume_dlq(
            settings=Settings(
                task_queue_provider="sqs",
                sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123/main",
            ),
            client=FakeSqsClient([]),
        )


def test_inspect_resume_dlq_bounds_limit():
    with pytest.raises(ValueError, match="between 1 and 10"):
        inspect_resume_dlq(settings=sqs_settings(), limit=11, client=FakeSqsClient([]))
