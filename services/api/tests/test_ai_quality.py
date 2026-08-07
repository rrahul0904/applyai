from sqlalchemy import select

from app.ai.quality import ai_quality_metrics
from app.career_models import AIArtifact, CandidateAIArtifactFeedback
from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs


def _seed_candidate_and_ai_artifact(client) -> str:
    with SessionLocal() as session:
        seed_development_jobs(session)
    profile = {
        "headline": "Senior data engineering leader",
        "current_title": "Senior Data Engineering Manager",
        "summary": "Data platform leader with 12 years of verified experience.",
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
                "description": "Led a 12-person data engineering organization.",
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
    matches = client.get("/api/v1/career-v1/matches?limit=1")
    assert matches.status_code == 200
    job_id = matches.json()["items"][0]["job_id"]
    run = client.post(f"/api/v1/career-v2/jobs/{job_id}/deep-match")
    assert run.status_code == 200
    assert run.json()["status"] == "COMPLETED"
    artifact = client.get(f"/api/v1/career-v2/artifacts?job_id={job_id}").json()["items"][0]
    return artifact["id"]


def test_ai_quality_metrics_are_measured_not_guessed(client):
    artifact_id = _seed_candidate_and_ai_artifact(client)

    feedback = client.post(
        f"/api/v1/career-v2/artifacts/{artifact_id}/feedback",
        json={"action": "ACCEPTED", "metadata": {"surface": "job-detail"}},
    )
    assert feedback.status_code == 200

    with SessionLocal() as session:
        artifact = session.get(AIArtifact, artifact_id)
        assert artifact is not None
        artifact.candidate_verified = True
        session.commit()

    with SessionLocal() as session:
        metrics = ai_quality_metrics(session, window_hours=24)
        assert metrics["runs"]["total"] == 1
        assert metrics["runs"]["completed"] == 1
        assert metrics["runs"]["success_rate"] == 1.0
        assert metrics["runs"]["by_task"]["AI_DEEP_MATCH"] == 1
        assert metrics["runs"]["by_provider"]["deterministic"] == 1
        assert metrics["usage"]["input_tokens"] == 0
        assert metrics["usage"]["output_tokens"] == 0
        assert metrics["usage"]["estimated_cost_usd"] == 0.0
        assert metrics["artifacts"]["total"] == 1
        assert metrics["artifacts"]["candidate_verified"] == 1
        assert metrics["artifacts"]["candidate_verification_rate"] == 1.0
        assert metrics["feedback"]["ACCEPTED"] == 1
        assert metrics["feedback"]["acceptance_rate"] == 1.0
        assert session.scalar(select(CandidateAIArtifactFeedback)) is not None
