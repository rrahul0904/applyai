from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.internal_worker import router
from app.core.config import Settings, get_settings


def build_client(settings: Settings) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_worker_drain_fails_closed_without_secret() -> None:
    with build_client(Settings(task_queue_provider="postgres")) as client:
        response = client.post("/api/v1/internal/worker/drain")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "WORKER_DRAIN_NOT_CONFIGURED"


def test_worker_drain_rejects_wrong_secret() -> None:
    with build_client(
        Settings(
            task_queue_provider="postgres",
            worker_drain_secret="this-is-a-long-worker-drain-secret",
        )
    ) as client:
        response = client.post(
            "/api/v1/internal/worker/drain",
            headers={"authorization": "Bearer wrong"},
        )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "WORKER_DRAIN_UNAUTHORIZED"


def test_worker_drain_processes_only_configured_batch(monkeypatch) -> None:
    observed = {}

    def fake_drain(settings, *, maximum_tasks):
        observed["provider"] = settings.task_queue_provider
        observed["maximum_tasks"] = maximum_tasks
        return 3

    monkeypatch.setattr("app.api.internal_worker.drain_bounded", fake_drain)
    secret = "this-is-a-long-worker-drain-secret"
    with build_client(
        Settings(
            task_queue_provider="postgres",
            worker_drain_secret=secret,
            worker_drain_batch_size=7,
        )
    ) as client:
        response = client.post(
            "/api/v1/internal/worker/drain",
            headers={"authorization": f"Bearer {secret}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "completed_tasks": 3,
        "maximum_tasks": 7,
    }
    assert observed == {"provider": "postgres", "maximum_tasks": 7}
