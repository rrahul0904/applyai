from datetime import datetime, timedelta, timezone
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

import app.api.career_radar as career_radar
import app.workers.radar_watch as radar_watch_worker

from app.api.career_radar import (
    _bucket,
    _effective_refresh_limit,
    _freshness_at,
    _recover_dead_postgres_run,
)
from app.career_models import AIJobRun, CareerMatch
from app.core.config import Settings
from app.core.database import SessionLocal
from app.durability_models import TaskOutbox
from app.jobs.dataset import build_seed_records
from app.jobs.seed import seed_development_jobs
from app.postgres_queue_models import PostgresTask
from app.radar_watch_models import RadarBucketTransition, RadarWatch
from app.workers.radar_watch import run_once as run_radar_watch_once


def profile_payload() -> dict:
    return {
        "headline": "Senior data engineering leader",
        "current_title": "Senior Data Engineering Manager",
        "summary": "Data platform leader building reliable cloud analytics platforms.",
        "years_experience": 12,
        "target_roles": ["Data Engineering Manager", "Analytics Engineering Manager"],
        "location_text": "Boston, MA",
        "work_modes": ["REMOTE", "HYBRID"],
        "minimum_compensation": 90000,
        "experiences": [
            {
                "company_name": "Atlas Health",
                "title": "Senior Data Engineering Manager",
                "start_date": "2021-01-01",
                "end_date": None,
                "description": (
                    "Led a cloud data engineering organization and modernized "
                    "analytics pipelines."
                ),
                "provenance": "USER_VERIFIED",
            }
        ],
        "education": [],
        "skills": [
            {"name": "Python", "provenance": "USER_VERIFIED"},
            {"name": "SQL", "provenance": "USER_VERIFIED"},
            {"name": "AWS", "provenance": "USER_VERIFIED"},
            {"name": "Snowflake", "provenance": "USER_VERIFIED"},
        ],
    }


def seed_recent_jobs(count: int = 4, *, posted_at: datetime | None = None) -> None:
    posted = (posted_at or datetime.now(timezone.utc)).isoformat()
    records = [
        {**record, "posted_at": posted}
        for record in build_seed_records()[:count]
    ]
    with SessionLocal() as session:
        seed_development_jobs(session, records=records)


def test_radar_bucket_tracks_current_and_legacy_decisions():
    assert _bucket(None) == "PENDING_JUDGMENT"
    assert _bucket(SimpleNamespace(decision="PRIORITIZE")) == "TOP_MATCH"
    assert _bucket(SimpleNamespace(decision="APPLY_NOW")) == "TOP_MATCH"
    assert _bucket(SimpleNamespace(decision="STRONG")) == "TOP_MATCH"
    assert _bucket(SimpleNamespace(decision="CONSIDER")) == "WATCH"
    assert _bucket(SimpleNamespace(decision="STRETCH")) == "LOW_PRIORITY"
    assert _bucket(SimpleNamespace(decision="SKIP")) == "LOW_PRIORITY"


def test_radar_freshness_prefers_newer_discovery_timestamp():
    now = datetime.now(timezone.utc)
    older = now - timedelta(days=60)
    job = SimpleNamespace(posted_at=older, first_seen_at=now)
    assert _freshness_at(job) == now


def test_request_triggered_postgres_refresh_respects_drain_capacity():
    settings = Settings(
        task_queue_provider="postgres",
        request_triggered_tasks_enabled=True,
        request_triggered_task_limit=1,
    )
    assert _effective_refresh_limit(10, settings) == 1

    memory = Settings(task_queue_provider="memory", request_triggered_tasks_enabled=True)
    assert _effective_refresh_limit(10, memory) == 10


def test_radar_includes_newly_discovered_job_with_old_posted_date(client):
    seed_recent_jobs(count=1, posted_at=datetime.now(timezone.utc) - timedelta(days=60))
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    response = client.get("/api/v1/career-v2/radar?limit=20&lookback_days=14")
    assert response.status_code == 200
    assert response.json()["items"]
    assert response.json()["counts"]["pending_judgment"] >= 1


def test_radar_counts_cover_full_window_not_only_limited_items(client):
    seed_recent_jobs(count=4)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    refresh = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    assert refresh.status_code == 200

    response = client.get("/api/v1/career-v2/radar?limit=1")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["returned"] == 1
    assert payload["total"] == 4
    assert sum(payload["counts"].values()) == 4
    assert payload["counts"]["pending_judgment"] == 3


def test_radar_refresh_judges_recent_unmatched_jobs(client):
    seed_recent_jobs()
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    initial = client.get("/api/v1/career-v2/radar?limit=20")
    assert initial.status_code == 200
    assert initial.json()["items"]
    assert initial.json()["counts"]["pending_judgment"] >= 1

    refresh = client.post("/api/v1/career-v2/radar/refresh?max_jobs=2")
    assert refresh.status_code == 200
    payload = refresh.json()
    assert payload["scheduled"] == 2
    assert payload["effective_max_jobs"] == 2
    assert payload["queue_limited"] is False
    assert len(payload["runs"]) == 2
    assert all(run["status"] == "COMPLETED" for run in payload["runs"])

    after = client.get("/api/v1/career-v2/radar?limit=20")
    assert after.status_code == 200
    judged = [item for item in after.json()["items"] if item["score"] is not None]
    assert len(judged) >= 2
    assert all(item["engine_version"] == "applyai-hybrid-fit-v2" for item in judged)
    assert all(item["reasons"] for item in judged)
    assert all(item["radar_bucket"] != "PENDING_JUDGMENT" for item in judged)

    with SessionLocal() as session:
        matches = list(session.scalars(select(CareerMatch)))
        assert len(matches) >= 2


def test_radar_refresh_retries_failed_idempotent_run(client):
    seed_recent_jobs(count=1)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    first = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    assert first.status_code == 200
    run_id = first.json()["runs"][0]["run_id"]

    with SessionLocal() as session:
        run = session.get(AIJobRun, run_id)
        assert run is not None
        match = session.scalar(
            select(CareerMatch).where(
                CareerMatch.user_id == run.user_id,
                CareerMatch.job_id == run.job_id,
            )
        )
        assert match is not None
        session.delete(match)
        run.status = "FAILED"
        run.error_code = "TEST_FAILURE"
        run.error_summary = "Synthetic failure used to verify Radar retry."
        session.commit()

    retried = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    assert retried.status_code == 200
    assert retried.json()["scheduled"] == 1
    assert retried.json()["runs"][0]["run_id"] == run_id
    assert retried.json()["runs"][0]["status"] == "COMPLETED"

    with SessionLocal() as session:
        run = session.get(AIJobRun, run_id)
        assert run is not None
        assert run.status == "COMPLETED"
        match = session.scalar(
            select(CareerMatch).where(
                CareerMatch.user_id == run.user_id,
                CareerMatch.job_id == run.job_id,
            )
        )
        assert match is not None


def test_radar_rearms_dead_postgres_delivery_after_explicit_refresh(client):
    seed_recent_jobs(count=1)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200
    first = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    run_id = first.json()["runs"][0]["run_id"]

    with SessionLocal() as session:
        run = session.get(AIJobRun, run_id)
        assert run is not None
        match = session.scalar(
            select(CareerMatch).where(
                CareerMatch.user_id == run.user_id,
                CareerMatch.job_id == run.job_id,
            )
        )
        assert match is not None
        session.delete(match)
        run.status = "QUEUED"
        run.error_code = "TRANSIENT_AI"
        run.error_summary = "Synthetic exhausted delivery."
        task = PostgresTask(
            task_type=run.task_type,
            payload={"run_id": str(run.id)},
            idempotency_key=f"ai-run:{run.id}",
            status="DEAD",
            attempt_count=3,
            last_error="TRANSIENT_AI",
        )
        session.add(task)
        session.commit()
        task_id = task.id

        recovered = _recover_dead_postgres_run(
            run,
            session=session,
            settings=Settings(
                task_queue_provider="postgres",
                request_triggered_tasks_enabled=True,
                request_triggered_task_limit=1,
            ),
        )
        assert recovered.status == "QUEUED"

        task = session.get(PostgresTask, task_id)
        assert task is not None
        assert task.status == "QUEUED"
        assert task.attempt_count == 0
        assert task.last_error is None
        assert run.error_code is None
        assert run.error_summary is None

        stale_outbox = list(
            session.scalars(
                select(TaskOutbox).where(
                    TaskOutbox.aggregate_type == "AIJobRun",
                    TaskOutbox.aggregate_id == run.id,
                    TaskOutbox.event_type == run.task_type,
                )
            )
        )
        assert stale_outbox
        assert all(item.status == "PUBLISHED" for item in stale_outbox)
        assert all(item.published_at is not None for item in stale_outbox)


def test_radar_refresh_skips_jobs_already_judged(client):
    seed_recent_jobs()
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    first = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    second = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["scheduled"] == 1
    assert second.json()["scheduled"] == 1
    assert first.json()["runs"][0]["job_id"] != second.json()["runs"][0]["job_id"]



def test_radar_records_bucket_transition_history(client):
    seed_recent_jobs(count=1)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    refresh = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    assert refresh.status_code == 200

    history = client.get("/api/v1/career-v2/radar/history")
    assert history.status_code == 200
    items = history.json()["items"]
    assert len(items) == 1
    assert items[0]["from_bucket"] == "PENDING_JUDGMENT"
    assert items[0]["to_bucket"] in {"TOP_MATCH", "WATCH", "LOW_PRIORITY"}

    with SessionLocal() as session:
        rows = list(session.scalars(select(RadarBucketTransition)))
        assert len(rows) == 1


def test_candidate_can_create_pause_and_run_radar_watch(client):
    seed_recent_jobs(count=2)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    created = client.post(
        "/api/v1/career-v2/radar/watches",
        json={
            "name": "Daily radar",
            "interval_minutes": 1440,
            "lookback_days": 14,
            "max_jobs": 2,
            "run_immediately": False,
        },
    )
    assert created.status_code == 200
    watch = created.json()
    assert watch["enabled"] is True

    listed = client.get("/api/v1/career-v2/radar/watches")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    paused = client.patch(
        f"/api/v1/career-v2/radar/watches/{watch['id']}",
        json={"enabled": False},
    )
    assert paused.status_code == 200
    assert paused.json()["enabled"] is False

    resumed = client.patch(
        f"/api/v1/career-v2/radar/watches/{watch['id']}",
        json={"enabled": True},
    )
    assert resumed.status_code == 200
    assert resumed.json()["enabled"] is True

    ran = client.post(f"/api/v1/career-v2/radar/watches/{watch['id']}/run")
    assert ran.status_code == 200
    assert ran.json()["watch"]["last_run_status"] == "SUCCEEDED"
    assert ran.json()["refresh"]["scheduled"] == 2


def test_due_radar_watch_runs_without_candidate_request(client):
    seed_recent_jobs(count=1)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200
    created = client.post(
        "/api/v1/career-v2/radar/watches",
        json={
            "name": "Hourly radar",
            "interval_minutes": 60,
            "lookback_days": 14,
            "max_jobs": 1,
            "run_immediately": False,
        },
    )
    watch_id = created.json()["id"]

    with SessionLocal() as session:
        watch = session.get(RadarWatch, uuid.UUID(watch_id))
        assert watch is not None
        watch.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    assert run_radar_watch_once(Settings(task_queue_provider="memory")) is True

    with SessionLocal() as session:
        watch = session.get(RadarWatch, uuid.UUID(watch_id))
        assert watch is not None
        assert watch.last_run_status == "SUCCEEDED"
        assert watch.last_scheduled_jobs == 1
        assert watch.next_run_at > datetime.now(timezone.utc)
        assert session.scalar(select(CareerMatch)) is not None


def test_radar_watch_worker_accepts_sqs_provider(monkeypatch):
    def stop_loop(*args, **kwargs):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(radar_watch_worker, "run_once", stop_loop)
    with pytest.raises(RuntimeError, match="stop-loop"):
        radar_watch_worker.run_worker(\n            Settings(\n                task_queue_provider="sqs",\n                sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/applyai-test",\n            )\n        )


def test_radar_watch_rejudgment_scan_reaches_beyond_first_page(monkeypatch):
    jobs = [SimpleNamespace(id=uuid.uuid4()) for _ in range(101)]
    matches = [SimpleNamespace(model_run_id=uuid.uuid4()) for _ in jobs]
    changed_job_id = jobs[-1].id

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def execute(self, statement):
            self.calls += 1
            if self.calls == 1:
                return list(zip(jobs[:100], matches[:100]))
            if self.calls == 2:
                return [(jobs[-1], matches[-1])]
            return []

    fake_session = FakeSession()
    monkeypatch.setattr(
        career_radar,
        "_refresh_radar_impl",
        lambda **kwargs: {
            "requested": 1,
            "scheduled": 0,
            "effective_max_jobs": 1,
            "queue_limited": False,
            "runs": [],
            "lookback_days": 14,
            "engine_version": career_radar.ENGINE_VERSION,
        },
    )
    monkeypatch.setattr(
        career_radar,
        "_match_needs_rejudgment",
        lambda session, *, user, job, match: job.id == changed_job_id,
    )
    queued_run = SimpleNamespace(id=uuid.uuid4(), status="COMPLETED")
    monkeypatch.setattr(career_radar, "_queue_run", lambda **kwargs: queued_run)

    result = career_radar.refresh_radar_watch(
        max_jobs=1,
        lookback_days=14,
        user=SimpleNamespace(id=uuid.uuid4()),
        session=fake_session,
        settings=Settings(task_queue_provider="memory"),
    )

    assert fake_session.calls == 2
    assert result["scheduled"] == 1
    assert result["rejudged"] == 1
    assert result["runs"][0]["job_id"] == str(changed_job_id)


def test_radar_watch_rejudges_material_candidate_change(client):
    seed_recent_jobs(count=1)
    original = profile_payload()
    assert client.put("/api/v1/profile", json=original).status_code == 200

    created = client.post(
        "/api/v1/career-v2/radar/watches",
        json={
            "name": "Material change radar",
            "interval_minutes": 1440,
            "lookback_days": 14,
            "max_jobs": 1,
            "run_immediately": False,
        },
    )
    watch_id = created.json()["id"]

    first = client.post(f"/api/v1/career-v2/radar/watches/{watch_id}/run")
    assert first.status_code == 200
    assert first.json()["refresh"]["scheduled"] == 1

    with SessionLocal() as session:
        first_runs = list(session.scalars(select(AIJobRun).where(AIJobRun.task_type == "AI_DEEP_MATCH")))
        assert len(first_runs) == 1
        first_run_id = first_runs[0].id

    changed = {**original, "summary": original["summary"] + " Added verified platform leadership evidence."}
    assert client.put("/api/v1/profile", json=changed).status_code == 200

    second = client.post(f"/api/v1/career-v2/radar/watches/{watch_id}/run")
    assert second.status_code == 200
    assert second.json()["refresh"]["scheduled"] == 1
    assert second.json()["refresh"]["rejudged"] == 1

    with SessionLocal() as session:
        runs = list(
            session.scalars(
                select(AIJobRun)
                .where(AIJobRun.task_type == "AI_DEEP_MATCH")
                .order_by(AIJobRun.created_at)
            )
        )
        assert len(runs) == 2
        assert runs[0].id == first_run_id
        assert runs[1].id != first_run_id


def test_radar_watch_ignores_last_seen_only_change(client):
    seed_recent_jobs(count=1)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200
    created = client.post(
        "/api/v1/career-v2/radar/watches",
        json={
            "name": "Stable radar",
            "interval_minutes": 1440,
            "lookback_days": 14,
            "max_jobs": 1,
            "run_immediately": False,
        },
    )
    watch_id = created.json()["id"]
    assert client.post(f"/api/v1/career-v2/radar/watches/{watch_id}/run").status_code == 200

    with SessionLocal() as session:
        match = session.scalar(select(CareerMatch))
        assert match is not None
        from app.models import Job

        job = session.get(Job, match.job_id)
        assert job is not None
        job.last_seen_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        session.commit()

    second = client.post(f"/api/v1/career-v2/radar/watches/{watch_id}/run")
    assert second.status_code == 200
    assert second.json()["refresh"]["scheduled"] == 0
    assert second.json()["refresh"]["rejudged"] == 0

    with SessionLocal() as session:
        runs = list(session.scalars(select(AIJobRun).where(AIJobRun.task_type == "AI_DEEP_MATCH")))
        assert len(runs) == 1



def test_radar_watch_claim_lease_prevents_duplicate_and_recovers_after_expiry(client):
    seed_recent_jobs(count=1)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200
    created = client.post(
        "/api/v1/career-v2/radar/watches",
        json={
            "name": "Lease radar",
            "interval_minutes": 60,
            "lookback_days": 14,
            "max_jobs": 1,
            "run_immediately": False,
        },
    )
    watch_id = uuid.UUID(created.json()["id"])
    now = datetime.now(timezone.utc)

    with SessionLocal() as session:
        watch = session.get(RadarWatch, watch_id)
        assert watch is not None
        watch.next_run_at = now - timedelta(minutes=1)
        session.commit()

    from app.workers.radar_watch import claim_due_watch

    settings = Settings(task_queue_provider="memory", radar_watch_lease_seconds=60)
    assert claim_due_watch(now, worker_id="worker-a", settings=settings) == watch_id
    assert claim_due_watch(now, worker_id="worker-b", settings=settings) is None

    with SessionLocal() as session:
        watch = session.get(RadarWatch, watch_id)
        assert watch is not None
        assert watch.lease_owner == "worker-a"
        assert watch.lease_expires_at is not None
        watch.lease_expires_at = now - timedelta(seconds=1)
        session.commit()

    assert claim_due_watch(now, worker_id="worker-b", settings=settings) == watch_id
    with SessionLocal() as session:
        watch = session.get(RadarWatch, watch_id)
        assert watch is not None
        assert watch.lease_owner == "worker-b"
