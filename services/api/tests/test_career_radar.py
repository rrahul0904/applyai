from types import SimpleNamespace

from sqlalchemy import select

from app.api.career_radar import _bucket
from app.career_models import CareerMatch
from app.core.database import SessionLocal
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


def test_radar_bucket_tracks_current_and_legacy_decisions():
    assert _bucket(None) == "PENDING_JUDGMENT"
    assert _bucket(SimpleNamespace(decision="PRIORITIZE")) == "TOP_MATCH"
    assert _bucket(SimpleNamespace(decision="APPLY_NOW")) == "TOP_MATCH"
    assert _bucket(SimpleNamespace(decision="STRONG")) == "TOP_MATCH"
    assert _bucket(SimpleNamespace(decision="CONSIDER")) == "WATCH"
    assert _bucket(SimpleNamespace(decision="STRETCH")) == "LOW_PRIORITY"
    assert _bucket(SimpleNamespace(decision="SKIP")) == "LOW_PRIORITY"


def test_radar_refresh_judges_recent_unmatched_jobs(client):
    with SessionLocal() as session:
        seed_development_jobs(session)

    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    initial = client.get("/api/v1/career-v2/radar?limit=20")
    assert initial.status_code == 200
    assert initial.json()["items"]
    assert initial.json()["counts"]["pending_judgment"] >= 1

    refresh = client.post("/api/v1/career-v2/radar/refresh?max_jobs=2")
    assert refresh.status_code == 200
    payload = refresh.json()
    assert payload["scheduled"] == 2
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


def test_radar_refresh_skips_jobs_already_judged(client):
    with SessionLocal() as session:
        seed_development_jobs(session)

    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200

    first = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    second = client.post("/api/v1/career-v2/radar/refresh?max_jobs=1")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["scheduled"] == 1
    assert second.json()["scheduled"] == 1
    assert first.json()["runs"][0]["job_id"] != second.json()["runs"][0]["job_id"]
