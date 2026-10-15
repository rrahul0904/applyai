from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app import worker_runtime
from app.core.config import Settings
from app.worker_runtime import WorkerHeartbeatStatus
from app.workers import postgres as postgres_worker


class _WriteSession:
    def __init__(self) -> None:
        self.statement = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement) -> None:
        self.statement = statement


class _WriteSessionFactory:
    def __init__(self) -> None:
        self.session = _WriteSession()

    def begin(self):
        return self.session


class _ReadSession:
    def __init__(self, row) -> None:
        self.row = row
        self.statement = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def scalar(self, statement):
        self.statement = statement
        return self.row


def test_record_worker_heartbeat_upserts_by_environment_type_and_identity(monkeypatch) -> None:
    factory = _WriteSessionFactory()
    monkeypatch.setattr(worker_runtime, "SessionLocal", factory)
    moment = datetime(2026, 10, 14, 12, tzinfo=UTC)

    worker_runtime.record_worker_heartbeat(
        environment="staging",
        worker_type="combined_worker",
        worker_id="ecs-task-123",
        deployment_sha="a" * 40,
        now=moment,
    )

    compiled = str(factory.session.statement.compile(dialect=postgresql.dialect()))
    params = factory.session.statement.compile(dialect=postgresql.dialect()).params
    assert "ON CONFLICT ON CONSTRAINT uq_worker_runtime_heartbeats_instance" in compiled
    assert params["environment"] == "staging"
    assert params["worker_type"] == "combined_worker"
    assert params["worker_id"] == "ecs-task-123"
    assert params["deployment_sha"] == "a" * 40
    assert params["heartbeat_at"] == moment


@pytest.mark.parametrize(
    ("age_seconds", "expected_healthy"),
    [(0, True), (30, True), (31, False), (-1, False)],
)
def test_latest_worker_heartbeat_reports_freshness(monkeypatch, age_seconds, expected_healthy) -> None:
    moment = datetime(2026, 10, 14, 12, tzinfo=UTC)
    row = SimpleNamespace(
        worker_id="worker-1",
        heartbeat_at=moment - timedelta(seconds=age_seconds),
        deployment_sha="f" * 40,
    )
    session = _ReadSession(row)
    monkeypatch.setattr(worker_runtime, "SessionLocal", lambda: session)

    result = worker_runtime.get_latest_worker_heartbeat(
        environment="staging",
        worker_type="combined_worker",
        max_age_seconds=30,
        now=moment,
    )

    assert isinstance(result, WorkerHeartbeatStatus)
    assert result.healthy is expected_healthy
    assert result.worker_id == "worker-1"
    assert result.deployment_sha == "f" * 40
    compiled = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "worker_runtime_heartbeats.environment = %(environment_1)s" in compiled
    assert "worker_runtime_heartbeats.worker_type = %(worker_type_1)s" in compiled
    params = session.statement.compile(dialect=postgresql.dialect()).params
    assert params["environment_1"] == "staging"
    assert params["worker_type_1"] == "combined_worker"


def test_latest_worker_heartbeat_is_unhealthy_when_no_worker_matches(monkeypatch) -> None:
    monkeypatch.setattr(worker_runtime, "SessionLocal", lambda: _ReadSession(None))

    result = worker_runtime.get_latest_worker_heartbeat(
        environment="production",
        worker_type="combined_worker",
        max_age_seconds=120,
    )

    assert result == WorkerHeartbeatStatus(False, None, None, None)


def test_deployment_sha_uses_runtime_release_identity(monkeypatch) -> None:
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "railway-sha")
    monkeypatch.setenv("GITHUB_SHA", "github-sha")
    assert worker_runtime.current_deployment_sha() == "railway-sha"


def test_combined_worker_emits_startup_heartbeat_with_deployment_sha(monkeypatch) -> None:
    stop = threading.Event()
    calls = []

    def record(**kwargs):
        calls.append(kwargs)
        stop.set()

    monkeypatch.setattr(postgres_worker, "record_worker_heartbeat", record)
    monkeypatch.setattr(postgres_worker, "current_deployment_sha", lambda: "release-sha")

    postgres_worker._runtime_heartbeat(
        settings=Settings(app_env="development", worker_runtime_heartbeat_seconds=5),
        worker_id="worker-1",
        stop=stop,
    )

    assert calls == [
        {
            "environment": "development",
            "worker_type": "combined_worker",
            "worker_id": "worker-1",
            "deployment_sha": "release-sha",
        }
    ]
