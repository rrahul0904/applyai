import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.outbox import add_task_outbox_event, publish_outbox_once
from app.core.queue import InMemoryTaskQueue, Task
from app.durability_models import TaskOutbox
from app.workers import source as source_worker


def test_outbox_routes_source_task_using_event_type(database_url, monkeypatch):
    engine = create_engine(database_url)
    source_queue = InMemoryTaskQueue()
    observed: list[str | None] = []

    def resolve_queue(settings, *, task_type=None):
        del settings
        observed.append(task_type)
        return source_queue

    monkeypatch.setattr("app.core.outbox.get_task_queue_for_type", resolve_queue)
    monkeypatch.setattr("app.core.outbox.SessionLocal", lambda: Session(engine))

    with Session(engine) as session:
        event = add_task_outbox_event(
            session,
            task=Task(
                task_type="SOURCE_INGEST",
                payload={"source_id": "00000000-0000-4000-8000-000000000001"},
                idempotency_key="source-ingest:test",
            ),
            aggregate_type="JOB_SOURCE_REGISTRY",
            aggregate_id="00000000-0000-4000-8000-000000000001",
        )
        session.commit()
        event_id = event.id

    assert publish_outbox_once(Settings(), queue=None, lock_owner="test-publisher") == 1
    assert observed == ["SOURCE_INGEST"]
    assert len(source_queue.tasks) == 1
    assert source_queue.tasks[0].task_type == "SOURCE_INGEST"
    with Session(engine) as session:
        persisted = session.get(TaskOutbox, event_id)
        assert persisted is not None and persisted.status == "PUBLISHED"
    engine.dispose()


def test_source_worker_routes_ingest_verify_and_discovery(monkeypatch):
    calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        source_worker,
        "process_source_ingest",
        lambda payload, settings: calls.append(("ingest", payload)) or True,
    )
    monkeypatch.setattr(
        source_worker,
        "verify_job_source_url",
        lambda source_id, settings: calls.append(("verify", {"id": str(source_id)})),
    )
    monkeypatch.setattr(
        source_worker,
        "process_discovery_message",
        lambda body, settings: calls.append(("discover", json.loads(body)["payload"])) or True,
    )

    settings = Settings()
    assert source_worker.process_message(
        json.dumps({"task_type": "SOURCE_INGEST", "payload": {"source_id": "x"}}),
        settings,
    ) is True
    assert source_worker.process_message(
        json.dumps(
            {
                "task_type": "SOURCE_VERIFY",
                "payload": {"job_source_id": "00000000-0000-4000-8000-000000000002"},
            }
        ),
        settings,
    ) is True
    assert source_worker.process_message(
        json.dumps({"task_type": "SOURCE_DISCOVERY", "payload": {"discovery_id": "d"}}),
        settings,
    ) is True
    assert [name for name, _ in calls] == ["ingest", "verify", "discover"]


def test_job_quality_api_requires_operator_token(client: TestClient):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        internal_api_token="operator-token-at-least-24-characters"
    )
    assert client.get("/api/v1/internal/job-quality/metrics").status_code == 403

    headers = {"X-ApplyAI-Internal-Token": "operator-token-at-least-24-characters"}
    metrics = client.get("/api/v1/internal/job-quality/metrics", headers=headers)
    coverage = client.get("/api/v1/internal/job-quality/source-coverage", headers=headers)
    assert metrics.status_code == 200
    assert coverage.status_code == 200
    assert metrics.json()["canonical_active_jobs"] == 0
    assert metrics.json()["measured_estimated_cost_usd"] is None
    assert coverage.json()["sources_by_type"] == {}
