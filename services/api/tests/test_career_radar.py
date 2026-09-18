from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select

from app.api.career_radar import _bucket, _effective_refresh_limit, _freshness_at
from app.career_models import AIJobRun, CareerMatch
from app.core.config import Settings
from app.core.database import SessionLocal
from app.jobs.dataset import build_seed_records
from app.jobs.seed import seed_development_jobs


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
