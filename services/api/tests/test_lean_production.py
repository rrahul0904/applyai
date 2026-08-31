from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.outbox import add_task_outbox_event, publish_outbox_once
from app.core.queue import (
    PostgresTaskQueue,
    Task,
    get_task_queue_for_type,
    supports_task_type,
)
from app.core.storage import S3ObjectStorageProvider
from app.durability_models import TaskOutbox
from app.postgres_queue_models import PostgresTask
from app.workers.postgres import (
    cancel_task,
    claim_task,
    dispatch_task,
    retry_or_dead_task,
    utcnow,
)


def _production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "deployment_profile": "lean",
        "database_url": "postgresql://user:secret@postgres.railway.internal:5432/railway",
        "auth_provider": "clerk",
        "clerk_issuer": "https://clerk.example.test",
        "clerk_jwks_url": "https://clerk.example.test/.well-known/jwks.json",
        "web_origin": "https://applyai.example.test",
        "object_storage_provider": "s3",
        "s3_bucket": "applyai-resumes",
        "s3_endpoint_url": "https://account.r2.cloudflarestorage.com",
        "s3_region": "auto",
        "s3_access_key_id": "r2-key",
        "s3_secret_access_key": "r2-secret",
        "s3_server_side_encryption": "none",
        "task_queue_provider": "postgres",
    }
    values.update(overrides)
    return Settings(**values)


def test_railway_database_url_is_normalized_for_psycopg() -> None:
    settings = Settings(database_url="postgresql://user:secret@db.internal:5432/applyai")
    assert settings.database_url == "postgresql+psycopg://user:secret@db.internal:5432/applyai"


def test_explicit_database_url_wins_over_legacy_split_database_fields() -> None:
    settings = Settings(
        database_url="postgresql://railway:secret@railway.internal:5432/railway",
        database_host="legacy.internal",
        database_name="legacy",
        database_user="legacy",
        database_password="legacy",
    )
    assert settings.database_url == "postgresql+psycopg://railway:secret@railway.internal:5432/railway"


def test_legacy_split_database_fields_remain_available_for_aws() -> None:
    settings = Settings(
        database_host="aurora.internal",
        database_name="applyai",
        database_user="applyai user",
        database_password="secret value",
    )
    assert settings.database_url == (
        "postgresql+psycopg://applyai%20user:secret%20value@aurora.internal:5432/applyai"
    )


def test_production_lean_profile_requires_postgres_queue_not_sqs() -> None:
    settings = _production_settings()
    assert settings.app_env == "production"
    assert settings.task_queue_provider == "postgres"
    assert settings.sqs_queue_url is None

    with pytest.raises(ValueError, match="lean profile requires TASK_QUEUE_PROVIDER=postgres"):
        _production_settings(task_queue_provider="memory")


def test_aws_profile_remains_compatible_with_sqs() -> None:
    settings = _production_settings(
        deployment_profile="aws",
        task_queue_provider="sqs",
        sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123/resume",
        sqs_dlq_url="https://sqs.us-east-1.amazonaws.com/123/resume-dlq",
        s3_endpoint_url=None,
        s3_region="us-east-1",
        s3_access_key_id=None,
        s3_secret_access_key=None,
        s3_server_side_encryption="AES256",
    )
    assert settings.deployment_profile == "aws"
    assert settings.task_queue_provider == "sqs"


class _FakeS3Client:
    def __init__(self) -> None:
        self.presign_params = None
        self.upload_extra_args = None

    def generate_presigned_url(self, _operation, *, Params, ExpiresIn, HttpMethod):
        self.presign_params = Params
        assert ExpiresIn == 900
        assert HttpMethod == "PUT"
        return "https://signed.example.test/upload"

    def upload_fileobj(self, _content, _bucket, _key, *, ExtraArgs):
        self.upload_extra_args = ExtraArgs


def test_r2_mode_omits_unsupported_aws_sse_header(monkeypatch) -> None:
    fake = _FakeS3Client()
    captured = {}

    def fake_client(service, **kwargs):
        assert service == "s3"
        captured.update(kwargs)
        return fake

    monkeypatch.setattr("app.core.storage.boto3.client", fake_client)
    storage = S3ObjectStorageProvider(_production_settings())
    url = storage.create_presigned_put(
        key="candidate/a/resume.pdf",
        content_type="application/pdf",
        expires_in_seconds=900,
    )

    assert url.startswith("https://")
    assert captured["endpoint_url"] == "https://account.r2.cloudflarestorage.com"
    assert captured["aws_access_key_id"] == "r2-key"
    assert "ServerSideEncryption" not in fake.presign_params
    assert storage.direct_upload_headers(content_type="application/pdf") == {
        "content-type": "application/pdf"
    }


def test_aws_s3_mode_preserves_aes256_sse(monkeypatch) -> None:
    fake = _FakeS3Client()
    monkeypatch.setattr("app.core.storage.boto3.client", lambda *_args, **_kwargs: fake)
    settings = Settings(
        object_storage_provider="s3",
        s3_bucket="applyai-aws-resumes",
        s3_server_side_encryption="AES256",
    )
    storage = S3ObjectStorageProvider(settings)
    storage.create_presigned_put(
        key="candidate/a/resume.pdf",
        content_type="application/pdf",
        expires_in_seconds=900,
    )
    assert fake.presign_params["ServerSideEncryption"] == "AES256"
    assert storage.direct_upload_headers(content_type="application/pdf")[
        "x-amz-server-side-encryption"
    ] == "AES256"


def test_postgres_queue_is_idempotent_and_outbox_safe(database_url) -> None:
    del database_url
    settings = Settings(task_queue_provider="postgres")
    queue = get_task_queue_for_type(settings, task_type="RESUME_PARSE")
    assert isinstance(queue, PostgresTaskQueue)
    task = Task(
        task_type="RESUME_PARSE",
        payload={"resume_version_id": str(uuid.uuid4())},
        idempotency_key="lean:test:resume",
    )

    queue.enqueue(task)
    queue.enqueue(task)
    with SessionLocal() as session:
        assert session.scalar(select(func.count(PostgresTask.id))) == 1

    aggregate_id = uuid.uuid4()
    with SessionLocal() as session:
        add_task_outbox_event(
            session,
            task=Task(
                task_type="RESUME_PARSE",
                payload={"resume_version_id": str(aggregate_id)},
                idempotency_key="lean:test:outbox",
            ),
            aggregate_type="RESUME_VERSION",
            aggregate_id=aggregate_id,
        )
        session.commit()

    assert publish_outbox_once(settings, lock_owner="test-publisher") == 1
    with SessionLocal() as session:
        assert session.scalar(select(func.count(PostgresTask.id))) == 2
        outbox = session.scalar(
            select(TaskOutbox).where(TaskOutbox.idempotency_key == "lean:test:outbox")
        )
        assert outbox is not None
        assert outbox.status == "PUBLISHED"


def test_postgres_queue_retries_with_backoff_before_dead_state(database_url) -> None:
    del database_url
    settings = Settings(
        task_queue_provider="postgres",
        postgres_task_lease_seconds=30,
        postgres_task_max_attempts=2,
        postgres_task_retry_base_seconds=1,
    )
    PostgresTaskQueue().enqueue(
        Task(task_type="RESUME_PARSE", payload={}, idempotency_key="lean:test:retry")
    )
    task_id = claim_task(settings, worker_id="worker-a")
    assert task_id is not None
    status = retry_or_dead_task(
        task_id,
        worker_id="worker-a",
        settings=settings,
        error_code="TRANSIENT",
    )
    assert status == "RETRY_WAIT"

    with SessionLocal() as session:
        row = session.get(PostgresTask, task_id)
        assert row is not None
        assert row.available_at > utcnow()
        row.available_at = utcnow() - timedelta(seconds=1)
        session.commit()

    assert claim_task(settings, worker_id="worker-b") == task_id
    status = retry_or_dead_task(
        task_id,
        worker_id="worker-b",
        settings=settings,
        error_code="TRANSIENT_AGAIN",
    )
    assert status == "DEAD"


def test_postgres_queue_recovers_expired_lease(database_url) -> None:
    del database_url
    settings = Settings(
        task_queue_provider="postgres",
        postgres_task_lease_seconds=30,
        postgres_task_max_attempts=3,
    )
    PostgresTaskQueue().enqueue(
        Task(task_type="RESUME_PARSE", payload={}, idempotency_key="lean:test:lease")
    )
    task_id = claim_task(settings, worker_id="worker-a")
    assert task_id is not None

    with SessionLocal() as session:
        row = session.get(PostgresTask, task_id)
        assert row is not None
        assert row.status == "RUNNING"
        assert row.attempt_count == 1
        row.lease_expires_at = utcnow() - timedelta(seconds=1)
        session.commit()

    reclaimed = claim_task(settings, worker_id="worker-b")
    assert reclaimed == task_id
    with SessionLocal() as session:
        row = session.get(PostgresTask, task_id)
        assert row is not None
        assert row.attempt_count == 2
        assert row.lease_owner == "worker-b"


def test_postgres_queue_cancellation_prevents_claim(database_url) -> None:
    del database_url
    settings = Settings(task_queue_provider="postgres")
    PostgresTaskQueue().enqueue(
        Task(task_type="RESUME_PARSE", payload={}, idempotency_key="lean:test:cancel")
    )
    with SessionLocal() as session:
        task_id = session.scalar(
            select(PostgresTask.id).where(PostgresTask.idempotency_key == "lean:test:cancel")
        )
    assert task_id is not None
    assert cancel_task(task_id) is True
    assert claim_task(settings, worker_id="worker-a") is None


def test_two_postgres_workers_claim_distinct_tasks(database_url) -> None:
    del database_url
    settings = Settings(task_queue_provider="postgres")
    queue = PostgresTaskQueue()
    queue.enqueue(Task(task_type="RESUME_PARSE", payload={}, idempotency_key="lean:test:worker-a"))
    queue.enqueue(Task(task_type="RESUME_PARSE", payload={}, idempotency_key="lean:test:worker-b"))

    def claim(worker_id: str):
        return claim_task(settings, worker_id=worker_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        task_ids = list(executor.map(claim, ["worker-a", "worker-b"]))

    assert all(task_ids)
    assert len(set(task_ids)) == 2
    with SessionLocal() as session:
        rows = list(session.scalars(select(PostgresTask).where(PostgresTask.id.in_(task_ids))))
        assert {row.lease_owner for row in rows} == {"worker-a", "worker-b"}


def test_postgres_queue_rejects_unknown_task_types(database_url) -> None:
    del database_url
    settings = Settings(task_queue_provider="postgres")
    assert supports_task_type(settings, "UNKNOWN") is False
    with pytest.raises(RuntimeError, match="UNSUPPORTED_POSTGRES_TASK_TYPE"):
        get_task_queue_for_type(settings, task_type="UNKNOWN")
    with pytest.raises(RuntimeError, match="UNSUPPORTED_POSTGRES_TASK_TYPE"):
        dispatch_task(Task(task_type="UNKNOWN", payload={}, idempotency_key="unknown"), settings)
