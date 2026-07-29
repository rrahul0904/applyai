import uuid
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.workers import resume as resume_worker
from app.workers.resume import process_message


DURABLE_SETTINGS = {
    "auth_provider": "clerk",
    "clerk_issuer": "https://clerk.example.test",
    "clerk_jwks_url": "https://clerk.example.test/.well-known/jwks.json",
    "object_storage_provider": "s3",
    "s3_bucket": "applyai-staging-resumes",
    "task_queue_provider": "sqs",
    "sqs_queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/applyai-resume",
    "web_origin": "https://staging.applyai.example",
}


def test_production_requires_durable_sqs_queue():
    with pytest.raises(ValueError, match="Production requires TASK_QUEUE_PROVIDER=sqs"):
        Settings(
            app_env="production",
            task_queue_provider="memory",
            auth_provider="clerk",
            clerk_issuer=DURABLE_SETTINGS["clerk_issuer"],
            clerk_jwks_url=DURABLE_SETTINGS["clerk_jwks_url"],
            object_storage_provider="s3",
            s3_bucket=DURABLE_SETTINGS["s3_bucket"],
            web_origin=DURABLE_SETTINGS["web_origin"],
        )


def test_sqs_provider_requires_queue_url():
    with pytest.raises(ValueError, match="SQS_QUEUE_URL"):
        Settings(task_queue_provider="sqs", sqs_queue_url=None)


def test_staging_requires_s3_storage():
    with pytest.raises(ValueError, match="Staging requires OBJECT_STORAGE_PROVIDER=s3"):
        Settings(
            app_env="staging",
            object_storage_provider="local",
            task_queue_provider="sqs",
            sqs_queue_url=DURABLE_SETTINGS["sqs_queue_url"],
            clerk_issuer=DURABLE_SETTINGS["clerk_issuer"],
            clerk_jwks_url=DURABLE_SETTINGS["clerk_jwks_url"],
            web_origin=DURABLE_SETTINGS["web_origin"],
        )


def test_credentialed_cors_rejects_wildcard_origin():
    with pytest.raises(ValueError, match="WEB_ORIGIN cannot be"):
        Settings(web_origin="*")


def test_visibility_heartbeat_must_be_shorter_than_visibility_timeout():
    with pytest.raises(ValueError, match="visibility heartbeat"):
        Settings(
            sqs_visibility_timeout_seconds=120,
            sqs_visibility_heartbeat_seconds=120,
        )


def test_sqs_production_configuration_is_accepted():
    settings = Settings(app_env="production", **DURABLE_SETTINGS)
    assert settings.task_queue_provider == "sqs"
    assert settings.object_storage_provider == "s3"
    assert settings.auth_provider == "clerk"


def test_resume_worker_acknowledges_unsupported_task_without_processing():
    settings = Settings()
    assert process_message('{"task_type":"UNKNOWN","payload":{}}', settings) is True


def test_resume_worker_retries_malformed_messages():
    settings = Settings()
    assert process_message("not-json", settings) is False
    assert process_message('{"task_type":"RESUME_PARSE","payload":{}}', settings) is False


def test_resume_worker_does_not_ack_active_processing_state(monkeypatch):
    resume_version_id = uuid.uuid4()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, model, value):
            del model, value
            return SimpleNamespace(processing_status="PROCESSING")

    monkeypatch.setattr(resume_worker, "get_object_storage", lambda settings: object())
    monkeypatch.setattr(
        resume_worker,
        "process_resume_version",
        lambda resume_version_id, storage: None,
    )
    monkeypatch.setattr(resume_worker, "SessionLocal", lambda: FakeSession())

    body = (
        '{"task_type":"RESUME_PARSE","payload":{"resume_version_id":"'
        + str(resume_version_id)
        + '"}}'
    )
    assert process_message(body, Settings()) is False
