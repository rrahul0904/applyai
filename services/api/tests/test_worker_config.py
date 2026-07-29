import pytest

from app.core.config import Settings
from app.workers.resume import process_message


def test_production_requires_durable_sqs_queue():
    with pytest.raises(ValueError, match="Production requires TASK_QUEUE_PROVIDER=sqs"):
        Settings(app_env="production", task_queue_provider="memory")


def test_sqs_provider_requires_queue_url():
    with pytest.raises(ValueError, match="SQS_QUEUE_URL"):
        Settings(task_queue_provider="sqs", sqs_queue_url=None)


def test_sqs_production_configuration_is_accepted():
    settings = Settings(
        app_env="production",
        task_queue_provider="sqs",
        sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/applyai-resume.fifo",
    )
    assert settings.task_queue_provider == "sqs"


def test_resume_worker_acknowledges_unsupported_task_without_processing():
    settings = Settings()
    assert process_message('{"task_type":"UNKNOWN","payload":{}}', settings) is True


def test_resume_worker_retries_malformed_messages():
    settings = Settings()
    assert process_message("not-json", settings) is False
    assert process_message('{"task_type":"RESUME_PARSE","payload":{}}', settings) is False
