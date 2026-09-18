from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.operator_auth import require_operator_or_internal
from app.interview_intelligence_service import build_lifecycle, report_fingerprint, skill_is_present
from app.main import app
from app.models import CandidateProfile, CandidateSkill, JobSkill, User
from tests.helpers import create_job


def _seed(database_url: str, client) -> str:
    assert client.get("/api/v1/me").status_code == 200
    engine = create_engine(database_url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "a@example.com"))
        assert user is not None
        profile = CandidateProfile(
            user_id=user.id,
            headline="Senior data platform leader",
            current_title="Data Architect",
            summary="Built machine learning data platforms and resilient analytics systems.",
            years_experience=11,
        )
        session.add(profile)
        session.flush()
        session.add_all(
            [
                CandidateSkill(profile_id=profile.id, name="Machine Learning", normalized_name="machine learning", proficiency="STRONG", provenance="USER_VERIFIED"),
                CandidateSkill(profile_id=profile.id, name="System Design", normalized_name="system design", proficiency="STRONG", provenance="USER_VERIFIED"),
            ]
        )
        job = create_job(session)
        session.add_all(
            [
                JobSkill(job_id=job.id, name="Machine Learning", normalized_name="machine learning", required=True),
                JobSkill(job_id=job.id, name="Kubernetes", normalized_name="kubernetes", required=True),
            ]
        )
        session.commit()
        job_id = str(job.id)
    engine.dispose()
    return job_id


def test_multi_word_skill_matching_does_not_create_false_gap() -> None:
    assert skill_is_present("machine learning", ["Machine Learning", "Python"])
    assert skill_is_present("machine learning", ["production machine learning systems"])
    assert skill_is_present("system design", ["distributed system design"])
    assert not skill_is_present("machine learning", ["machine"])
    assert not skill_is_present("system design", ["design"])
    assert not skill_is_present("kubernetes", ["machine learning", "system design"])


def test_lifecycle_regeneration_preserves_notes_and_carry_forward() -> None:
    first = build_lifecycle(
        job_title="Data Architect",
        company="Example Co",
        candidate_skills=["machine learning"],
        required_skills=["machine learning", "kubernetes"],
    )
    first["phases"][0]["notes"] = "Ask about platform ownership."
    first["phases"][0]["carry_forward"] = ["Practice the migration example"]
    regenerated = build_lifecycle(
        job_title="Data Architect",
        company="Example Co",
        candidate_skills=["machine learning"],
        required_skills=["machine learning", "kubernetes"],
        prior=first,
    )
    assert regenerated["phases"][0]["notes"] == "Ask about platform ownership."
    assert regenerated["phases"][0]["carry_forward"] == ["Practice the migration example"]
    assert regenerated["carry_forward"] == ["Practice the migration example"]
    assert regenerated["strengths"] == ["machine learning"]
    assert regenerated["gaps"] == ["kubernetes"]


def test_report_fingerprint_is_whitespace_and_case_stable() -> None:
    first = report_fingerprint(company="Example Co", role="Data Architect", stage="Screen", body="Asked about system design.")
    second = report_fingerprint(company=" example co ", role="DATA ARCHITECT", stage="screen", body="Asked   about system design.")
    assert first == second


def test_interview_intelligence_end_to_end_and_evidence_reversal(client, database_url) -> None:
    job_id = _seed(database_url, client)

    created = client.post(
        f"/api/v1/interview-intelligence/workspaces/{job_id}",
        json={
            "interview_date": "2026-10-01T15:00:00Z",
            "interviewer_name": "Casey Morgan",
            "interviewer_title": "VP Engineering",
            "interviewer_url": "https://example.com/interviewer",
        },
    )
    assert created.status_code == 201, created.text
    workspace = created.json()
    assert workspace["current_phase_number"] == 1
    assert len(workspace["lifecycle"]["phases"]) == 4
    assert "machine learning" in workspace["lifecycle"]["strengths"]
    assert "kubernetes" in workspace["lifecycle"]["gaps"]
    assert len(workspace["podcasts"]) == 5
    assert workspace["interviewer"]["name"] == "Casey Morgan"
    assert workspace["interviewer"]["title"] == "VP Engineering"

    notes = client.put(
        f"/api/v1/interview-intelligence/workspaces/{job_id}/phases/1/notes",
        json={"notes": "Ask about platform ownership."},
    )
    assert notes.status_code == 200, notes.text

    cannot_skip = client.post(
        f"/api/v1/interview-intelligence/workspaces/{job_id}/phases/2/reflection",
        json={"how_it_went": "Not yet"},
    )
    assert cannot_skip.status_code == 409

    reflected = client.post(
        f"/api/v1/interview-intelligence/workspaces/{job_id}/phases/1/reflection",
        json={
            "how_it_went": "Strong evidence discussion.",
            "prepare_differently": "Practice the migration trade-off story.",
            "difficult_questions": ["How did you measure adoption?"],
        },
    )
    assert reflected.status_code == 200, reflected.text
    assert reflected.json()["current_phase_number"] == 2
    assert "Practice the migration trade-off story." in reflected.json()["lifecycle"]["carry_forward"]

    regenerated = client.post(f"/api/v1/interview-intelligence/workspaces/{job_id}", json={"regenerate": True})
    assert regenerated.status_code == 201, regenerated.text
    assert regenerated.json()["lifecycle"]["phases"][0]["notes"] == "Ask about platform ownership."
    assert "Practice the migration trade-off story." in regenerated.json()["lifecycle"]["carry_forward"]
    assert regenerated.json()["interviewer"]["name"] == "Casey Morgan"
    assert regenerated.json()["interviewer"]["title"] == "VP Engineering"

    questions = client.get("/api/v1/interview-intelligence/questions")
    assert questions.status_code == 200, questions.text
    assert questions.json()["total"] >= 0
    if not questions.json()["items"]:
        app.dependency_overrides[require_operator_or_internal] = lambda: None
        try:
            seeded = client.post(
                "/api/v1/internal/interview-intelligence/questions",
                json={
                    "title": "Design a resilient high-scale service",
                    "track": "SYSTEM_DESIGN",
                    "difficulty": "HARD",
                    "summary": "Clean-room system-design practice.",
                    "prompt": "Design a resilient high-scale service and explain trade-offs, failure modes, and verification.",
                    "skills": ["architecture", "reliability"],
                    "patterns": ["capacity planning", "failure modes"],
                    "hints": ["Clarify requirements first."],
                    "follow_ups": ["What changes at 10x scale?"],
                    "solution_outline": ["Clarify", "Model", "Trade-offs", "Verify"],
                    "frequency_score": 25,
                    "published": True,
                },
            )
            assert seeded.status_code == 201, seeded.text
        finally:
            app.dependency_overrides.pop(require_operator_or_internal, None)
        questions = client.get("/api/v1/interview-intelligence/questions")
        assert questions.status_code == 200, questions.text
    question = questions.json()["items"][0]

    attempt = client.post(
        "/api/v1/interview-intelligence/attempts",
        json={
            "question_id": question["id"],
            "job_id": job_id,
            "answer_text": "I would clarify requirements, compare trade-offs, test failure modes, monitor metrics, and verify the outcome before production rollout.",
        },
    )
    assert attempt.status_code == 201, attempt.text
    assert attempt.json()["score"] > 0
    assert client.get("/api/v1/interview-intelligence/progress").json()["total_attempts"] == 1

    report = client.post(
        "/api/v1/interview-intelligence/reports",
        json={
            "company": "Example Co",
            "role": "Data Architect",
            "interview_stage": "Technical",
            "title": "Technical interview experience",
            "body": "I was asked to reason through a resilient platform design and explain the operational trade-offs in detail.",
        },
    )
    assert report.status_code == 201, report.text
    report_id = report.json()["id"]

    app.dependency_overrides[require_operator_or_internal] = lambda: None
    try:
        approved = client.post(
            f"/api/v1/internal/interview-intelligence/reports/{report_id}/moderate",
            json={"decision": "APPROVED"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["moderation_status"] == "APPROVED_UNLINKED"

        queue = client.get("/api/v1/internal/interview-intelligence/reports")
        assert queue.status_code == 200
        assert any(item["id"] == report_id for item in queue.json())

        catalog = client.get("/api/v1/internal/interview-intelligence-catalog/questions")
        assert catalog.status_code == 200, catalog.text
        question_id = catalog.json()[0]["id"]
        linked = client.post(
            f"/api/v1/internal/interview-intelligence/reports/{report_id}/evidence",
            json={"question_id": question_id, "confidence": 90, "evidence_notes": "Firsthand user report"},
        )
        assert linked.status_code == 200, linked.text
        assert linked.json()["moderation_status"] == "APPROVED_LINKED"
        assert linked.json()["question"]["report_count"] == 1
        assert "Example Co" in linked.json()["question"]["companies"]

        evidence = client.get("/api/v1/internal/interview-intelligence-catalog/evidence")
        evidence_id = next(item["id"] for item in evidence.json() if item["report_id"] == report_id)
        unlinked = client.delete(f"/api/v1/internal/interview-intelligence/evidence/{evidence_id}")
        assert unlinked.status_code == 200, unlinked.text
        assert unlinked.json()["report_status"] == "APPROVED_UNLINKED"
        assert unlinked.json()["question"]["report_count"] == 0
        assert "Example Co" not in unlinked.json()["question"]["companies"]

        approved_again = client.post(
            f"/api/v1/internal/interview-intelligence/reports/{report_id}/moderate",
            json={"decision": "APPROVED"},
        )
        assert approved_again.status_code == 200
        relinked = client.post(
            f"/api/v1/internal/interview-intelligence/reports/{report_id}/evidence",
            json={"question_id": question_id, "confidence": 90, "evidence_notes": "Firsthand user report"},
        )
        assert relinked.status_code == 200
        assert relinked.json()["question"]["report_count"] == 1

        rejected = client.post(
            f"/api/v1/internal/interview-intelligence/reports/{report_id}/moderate",
            json={"decision": "REJECTED"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["moderation_status"] == "REJECTED"
        catalog_after_reject = client.get("/api/v1/internal/interview-intelligence-catalog/questions")
        rejected_question = next(item for item in catalog_after_reject.json() if item["id"] == question_id)
        assert rejected_question["report_count"] == 0
        assert "Example Co" not in rejected_question["companies"]
    finally:
        app.dependency_overrides.pop(require_operator_or_internal, None)
