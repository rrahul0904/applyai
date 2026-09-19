import json

import pytest

from app.core.config import Settings
from app.core.queue import (
    InMemoryTaskQueue,
    PostgresTaskQueue,
    get_task_queue_for_type,
    supports_task_type,
)
from app.workers import source as source_worker


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
    assert supports_task_type(settings, "JOB_URL_IMPORT") is True
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



def test_postgres_provider_accepts_candidate_job_url_imports():
    settings = Settings(task_queue_provider="postgres")
    assert supports_task_type(settings, "JOB_URL_IMPORT") is True
    assert isinstance(
        get_task_queue_for_type(settings, task_type="JOB_URL_IMPORT"),
        PostgresTaskQueue,
    )


def test_source_worker_dispatches_candidate_job_url_import(monkeypatch):
    observed = {}

    def fake_discovery(body: str, settings: Settings) -> bool:
        observed["body"] = json.loads(body)
        observed["provider"] = settings.task_queue_provider
        return True

    monkeypatch.setattr(source_worker, "process_discovery_message", fake_discovery)
    settings = Settings(task_queue_provider="postgres")
    body = json.dumps(
        {
            "task_type": "JOB_URL_IMPORT",
            "payload": {"discovery_id": "00000000-0000-0000-0000-000000000001"},
            "idempotency_key": "job-url-import:test",
        }
    )

    assert source_worker.process_message(body, settings) is True
    assert observed["body"]["task_type"] == "JOB_URL_IMPORT"
    assert observed["provider"] == "postgres"


def test_job_url_import_uses_default_sqs_when_dedicated_source_queue_is_absent(monkeypatch):
    settings = _sqs_settings(source_sqs_queue_url=None)
    captured = {}

    class FakeClient:
        def send_message(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "app.core.queue.sqs_client",
        lambda *, region: FakeClient(),
    )
    queue = get_task_queue_for_type(settings, task_type="JOB_URL_IMPORT")
    assert queue.queue_url == settings.sqs_queue_url
