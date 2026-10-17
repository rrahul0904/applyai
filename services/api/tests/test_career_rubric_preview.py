from sqlalchemy import func, select

from app.career_models import AIJobRun
from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs


def _seed_profile_and_job(client) -> str:
    with SessionLocal() as session:
        seed_development_jobs(session)

    profile = {
        "headline": "Senior data engineer",
        "current_title": "Senior Data Engineer",
        "summary": "Builds governed production data platforms.",
        "years_experience": 10,
        "target_roles": ["Senior Data Architect"],
        "location_text": "Boston, MA",
        "work_modes": ["REMOTE", "HYBRID"],
        "minimum_compensation": 90000,
        "experiences": [
            {
                "company_name": "Example Co",
                "title": "Senior Data Engineer",
                "start_date": "2021-01-01",
                "end_date": None,
                "description": "Owned architecture decisions for a governed data platform.",
                "provenance": "USER_VERIFIED",
            }
        ],
        "education": [],
        "skills": [
            {"name": "Python", "provenance": "USER_VERIFIED"},
            {"name": "SQL", "provenance": "USER_VERIFIED"},
        ],
    }
    assert client.put("/api/v1/profile", json=profile).status_code == 200
    matches = client.get("/api/v1/career-v1/matches?limit=20")
    assert matches.status_code == 200
    items = matches.json()["items"]
    assert items
    return items[0]["job_id"]


def _ai_run_count() -> int:
    with SessionLocal() as session:
        return int(session.scalar(select(func.count()).select_from(AIJobRun)) or 0)


def test_rubric_preview_is_read_only_and_conservative(client):
    job_id = _seed_profile_and_job(client)
    before_runs = _ai_run_count()

    response = client.get(
        f"/api/v1/career-v2/jobs/{job_id}/rubric-assessment-preview"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "DETERMINISTIC_PREVIEW"
    assert payload["rubric"]["version"] == "career-rubric-v1"
    assert payload["assessment"]["assessment_id"].startswith("cra_")
    assert payload["assessment"]["candidate_revision"].startswith("candidate-sha256:")
    assert payload["assessment"]["job_revision"].startswith("job-sha256:")
    assert len(payload["assessment"]["results"]) == 7
    assert payload["unclassified_job_requirements"]
    assert any(
        "not inferred from titles" in limitation
        for limitation in payload["limitations"]
    )
    assert _ai_run_count() == before_runs

    by_dimension = {
        row["dimension_id"]: row for row in payload["assessment"]["results"]
    }
    assert by_dimension["leadership_influence"]["coverage"] == "unknown"
    assert by_dimension["role_level_consistency"]["coverage"] == "unknown"
