from sqlalchemy import select

from app.career_memory_models import CandidateCareerFact
from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs


def seed_jobs() -> None:
    with SessionLocal() as session:
        seed_development_jobs(session)


def profile_payload() -> dict:
    return {
        "headline": "Senior data engineering leader",
        "current_title": "Senior Data Engineering Manager",
        "summary": "Data platform leader with 12 years of experience.",
        "years_experience": 12,
        "target_roles": ["Data Engineering Manager"],
        "location_text": "Boston, MA",
        "work_modes": ["REMOTE", "HYBRID"],
        "minimum_compensation": 90000,
        "experiences": [
            {
                "company_name": "Atlas Health",
                "title": "Senior Data Engineering Manager",
                "start_date": "2021-01-01",
                "end_date": None,
                "description": "Built and led a 12-person data engineering organization.",
                "provenance": "USER_VERIFIED",
            }
        ],
        "education": [],
        "skills": [
            {"name": "Python", "provenance": "USER_VERIFIED"},
            {"name": "SQL", "provenance": "USER_VERIFIED"},
        ],
    }


def test_career_memory_crud_and_summary(client):
    created = client.post(
        "/api/v1/career-memory",
        json={
            "category": "ACHIEVEMENT",
            "title": "Platform migration",
            "fact_text": "Led a verified migration that reduced pipeline delivery time by 35%.",
            "tags": ["data-platform", "leadership"],
            "occurred_at": "2025-05-01",
        },
    )
    assert created.status_code == 201
    fact_id = created.json()["id"]
    assert created.json()["user_verified"] is True
    assert created.json()["provenance"] == "USER_VERIFIED"

    listed = client.get("/api/v1/career-memory")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [fact_id]

    summary = client.get("/api/v1/career-memory/summary")
    assert summary.status_code == 200
    assert summary.json()["verified_fact_count"] == 1
    assert summary.json()["by_category"]["ACHIEVEMENT"] == 1

    updated = client.patch(
        f"/api/v1/career-memory/{fact_id}",
        json={"tags": ["leadership", "migration"]},
    )
    assert updated.status_code == 200
    assert updated.json()["tags"] == ["leadership", "migration"]

    archived = client.delete(f"/api/v1/career-memory/{fact_id}")
    assert archived.status_code == 204
    assert client.get("/api/v1/career-memory").json() == []


def test_verified_career_memory_is_available_to_ai_context(client):
    seed_jobs()
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200
    created = client.post(
        "/api/v1/career-memory",
        json={
            "category": "METRIC",
            "title": "Delivery improvement",
            "fact_text": "Reduced pipeline delivery time by 35% after a platform redesign.",
            "tags": ["delivery"],
        },
    )
    assert created.status_code == 201
    fact_id = created.json()["id"]

    matches = client.get("/api/v1/career-v1/matches?limit=1")
    assert matches.status_code == 200
    job_id = matches.json()["items"][0]["job_id"]
    run = client.post(f"/api/v1/career-v2/jobs/{job_id}/deep-match")
    assert run.status_code == 200
    assert run.json()["status"] == "COMPLETED"

    with SessionLocal() as session:
        fact = session.get(CandidateCareerFact, fact_id)
        assert fact is not None
        evidence_key = f"candidate.career_fact.{fact.id}"
        run_row = session.execute(
            select(__import__("app.career_models", fromlist=["AIJobRun"]).AIJobRun)
        ).scalar_one()
        assert evidence_key in run_row.input_json["evidence_catalog"]
