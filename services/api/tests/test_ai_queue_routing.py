import pytest

from app.core.config import Settings
from app.core.queue import (
    InMemoryTaskQueue,
    get_task_queue_for_type,
    supports_task_type,
)


def _sqs_settings(**overrides) -> Settings:
    values = {
        "environment": "development",
        "task_queue_provider": "sqs",
        "sqs_queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/resume",
        "sqs_dlq_url": "https://sqs.us-east-1.amazonaws.com/123456789012/resume-dlq",
    }
    values.update(overrides)
    return Settings(**values)


def test_specialized_sqs_tasks_fail_closed_without_dedicated_queue():
    settings = _sqs_settings()
    assert supports_task_type(settings, "RESUME_PARSE") is True
    assert supports_task_type(settings, "SOURCE_INGEST") is False
    assert supports_task_type(settings, "AI_DEEP_MATCH") is False

    with pytest.raises(RuntimeError, match="dedicated source queue"):
        get_task_queue_for_type(settings, task_type="SOURCE_INGEST")
    with pytest.raises(RuntimeError, match="dedicated AI queue"):
        get_task_queue_for_type(settings, task_type="AI_DEEP_MATCH")


def test_memory_provider_keeps_task_families_isolated():
    settings = Settings(task_queue_provider="memory")
    resume = get_task_queue_for_type(settings, task_type="RESUME_PARSE")
    source = get_task_queue_for_type(settings, task_type="SOURCE_INGEST")
    ai = get_task_queue_for_type(settings, task_type="AI_DEEP_MATCH")

    assert isinstance(resume, InMemoryTaskQueue)
    assert isinstance(source, InMemoryTaskQueue)
    assert isinstance(ai, InMemoryTaskQueue)
    assert resume is not source
    assert resume is not ai
    assert source is not ai
