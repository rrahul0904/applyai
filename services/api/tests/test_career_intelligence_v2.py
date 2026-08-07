from sqlalchemy import select

from app.career_models import (
    AIArtifact,
    AIJobRun,
    ApplicationQuestionDraft,
    CareerMatch,
    CoverLetter,
    ResumeTailoring,
    ResumeTailoringRevision,
)
from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs


def seed_jobs() -> None:
    with SessionLocal() as session:
        seed_development_jobs(session)


def profile_payload() -> dict:
    return {
        "headline": "Senior data engineering leader",
        "current_title": "Senior Data Engineering Manager",
        "summary": (
            "Data platform leader with 12 years of experience building reliable "
            "analytics and machine-learning infrastructure."
        ),
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
                    "Built and led a 12-person data engineering organization and "
                    "reduced pipeline delivery time by 35%."
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


def _selected_job(client) -> str:
    matches = client.get("/api/v1/career-v1/matches?limit=10")
    assert matches.status_code == 200
    return str(matches.json()["items"][0]["job_id"])


def test_career_v2_materializes_evidence_locked_artifacts(client):
    seed_jobs()
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200
    job_id = _selected_job(client)

    deep_match = client.post(f"/api/v1/career-v2/jobs/{job_id}/deep-match")
    assert deep_match.status_code == 200
    assert deep_match.json()["status"] == "COMPLETED"
    assert deep_match.json()["provider"] == "deterministic"
    assert deep_match.json()["output"]["ai_score"] >= 0
    assert deep_match.json()["evidence_refs"]

    resume = client.post(f"/api/v1/career-v2/jobs/{job_id}/resume-tailoring")
    assert resume.status_code == 200
    assert resume.json()["status"] == "COMPLETED"
    assert resume.json()["application_id"] is not None

    copilot = client.post(f"/api/v1/career-v2/jobs/{job_id}/application-copilot")
    assert copilot.status_code == 200
    assert copilot.json()["status"] == "COMPLETED"

    interview = client.post(f"/api/v1/career-v2/jobs/{job_id}/interview-prep")
    assert interview.status_code == 200
    assert interview.json()["status"] == "COMPLETED"
    assert len(interview.json()["output"]["likely_questions"]) >= 3

    artifacts = client.get(f"/api/v1/career-v2/artifacts?job_id={job_id}")
    assert artifacts.status_code == 200
    artifact_types = {item["artifact_type"] for item in artifacts.json()["items"]}
    assert {"DEEP_MATCH", "RESUME_TAILORING", "APPLICATION_COPILOT", "INTERVIEW_PREP"} <= artifact_types

    with SessionLocal() as session:
        runs = list(session.scalars(select(AIJobRun)))
        assert len(runs) == 4
        assert all(run.status == "COMPLETED" for run in runs)
        assert all(run.evidence_refs for run in runs)
        assert session.scalar(select(CareerMatch)) is not None
        tailoring = session.scalar(select(ResumeTailoring))
        assert tailoring is not None
        revision = session.scalar(
            select(ResumeTailoringRevision).where(
                ResumeTailoringRevision.tailoring_id == tailoring.id
            )
        )
        assert revision is not None
        assert revision.candidate_decision == "PENDING"
        cover = session.scalar(select(CoverLetter))
        assert cover is not None
        question = session.scalar(select(ApplicationQuestionDraft))
        assert question is not None

    review = client.patch(
        f"/api/v1/career-v2/tailorings/{tailoring.id}/revisions/{revision.position}",
        json={"decision": "APPROVED", "text": revision.suggested_text},
    )
    assert review.status_code == 200
    assert review.json()["decision"] == "APPROVED"

    cover_review = client.patch(
        f"/api/v1/career-v2/cover-letters/{cover.id}",
        json={"body": cover.body, "candidate_verified": True},
    )
    assert cover_review.status_code == 200
    assert cover_review.json()["candidate_verified"] is True

    question_review = client.patch(
        f"/api/v1/career-v2/question-drafts/{question.id}",
        json={"answer": question.draft, "candidate_verified": True},
    )
    assert question_review.status_code == 200
    assert question_review.json()["candidate_verified"] is True


def test_career_v2_is_idempotent_for_unchanged_evidence(client):
    seed_jobs()
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200
    job_id = _selected_job(client)

    first = client.post(f"/api/v1/career-v2/jobs/{job_id}/deep-match")
    second = client.post(f"/api/v1/career-v2/jobs/{job_id}/deep-match")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    with SessionLocal() as session:
        assert len(list(session.scalars(select(AIJobRun)))) == 1
        assert len(list(session.scalars(select(AIArtifact)))) == 1
