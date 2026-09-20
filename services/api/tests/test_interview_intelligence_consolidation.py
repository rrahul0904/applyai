from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.operator_auth import require_operator_or_internal
from app.interview_intelligence_models import InterviewIntelligenceQuestion, InterviewQuestionAttempt
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



def test_company_question_bank_filters_and_per_question_progress(client, database_url) -> None:
    job_id = _seed(database_url, client)

    app.dependency_overrides[require_operator_or_internal] = lambda: None
    try:
        created = client.post(
            "/api/v1/internal/interview-intelligence/questions",
            json={
                "title": "Design a bounded work queue",
                "slug": "test-bounded-work-queue",
                "track": "CODING",
                "difficulty": "HARD",
                "summary": "Clean-room coding practice for bounded work scheduling and explicit backpressure.",
                "prompt": "Design a bounded work queue, explain concurrency trade-offs, and describe how you would verify correctness under load.",
                "companies": ["Example Co"],
                "stages": ["SCREENING", "ONSITE"],
                "skills": ["concurrency", "backpressure"],
                "patterns": ["queue", "worker pool"],
                "hints": ["Start by defining capacity and producer behavior."],
                "follow_ups": ["How would priorities change the design?"],
                "solution_outline": ["Define invariants", "Bound capacity", "Coordinate workers", "Test overload"],
                "frequency_score": 60,
                "published": True,
            },
        )
        assert created.status_code == 201, created.text
        question = created.json()

        catalog = client.get("/api/v1/internal/interview-intelligence-catalog/questions")
        assert catalog.status_code == 200, catalog.text
        catalog_item = next(item for item in catalog.json() if item["id"] == question["id"])
        assert catalog_item["stages"] == ["SCREENING", "ONSITE"]
    finally:
        app.dependency_overrides.pop(require_operator_or_internal, None)

    filtered = client.get(
        "/api/v1/interview-intelligence/questions",
        params={
            "company": "example co",
            "stage": "screening",
            "track": "CODING",
            "difficulty": "HARD",
            "sort": "confidence",
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 1
    item = filtered.json()["items"][0]
    assert item["id"] == question["id"]
    assert item["stages"] == ["SCREENING", "ONSITE"]

    recent_only = client.get(
        "/api/v1/interview-intelligence/questions",
        params={"company": "Example Co", "reported_within_days": 90},
    )
    assert recent_only.status_code == 200, recent_only.text
    assert recent_only.json()["total"] == 0

    app.dependency_overrides[require_operator_or_internal] = lambda: None
    try:
        older = client.post(
            "/api/v1/internal/interview-intelligence/questions",
            json={
                "title": "Older evidence-backed queue design",
                "slug": "test-older-evidence-queue",
                "track": "CODING",
                "difficulty": "HARD",
                "summary": "Clean-room queue practice with older evidence for deterministic recency ordering.",
                "prompt": "Design a queue and explain how you would validate bounded concurrency and overload behavior.",
                "companies": ["Example Co"],
                "stages": ["SCREENING"],
                "skills": ["concurrency"],
                "patterns": ["queue"],
                "frequency_score": 40,
                "published": True,
            },
        )
        newer = client.post(
            "/api/v1/internal/interview-intelligence/questions",
            json={
                "title": "Newer evidence-backed queue design",
                "slug": "test-newer-evidence-queue",
                "track": "CODING",
                "difficulty": "HARD",
                "summary": "Clean-room queue practice with newer evidence for deterministic recency ordering.",
                "prompt": "Design a queue and explain how you would validate worker coordination and overload behavior.",
                "companies": ["Example Co"],
                "stages": ["SCREENING"],
                "skills": ["concurrency"],
                "patterns": ["worker pool"],
                "frequency_score": 30,
                "published": True,
            },
        )
        assert older.status_code == 201, older.text
        assert newer.status_code == 201, newer.text
    finally:
        app.dependency_overrides.pop(require_operator_or_internal, None)

    engine = create_engine(database_url)
    with Session(engine) as session:
        baseline = session.get(InterviewIntelligenceQuestion, question["id"])
        older_row = session.get(InterviewIntelligenceQuestion, older.json()["id"])
        newer_row = session.get(InterviewIntelligenceQuestion, newer.json()["id"])
        assert baseline is not None and older_row is not None and newer_row is not None
        baseline.last_reported_at = None
        baseline.confidence = 35
        older_row.last_reported_at = datetime.now(timezone.utc) - timedelta(days=20)
        older_row.confidence = 70
        newer_row.last_reported_at = datetime.now(timezone.utc) - timedelta(days=2)
        newer_row.confidence = 90
        session.commit()
    engine.dispose()

    recent_sorted = client.get(
        "/api/v1/interview-intelligence/questions",
        params={"company": "Example Co", "track": "CODING", "difficulty": "HARD", "sort": "recent"},
    )
    assert recent_sorted.status_code == 200, recent_sorted.text
    recent_ids = [row["id"] for row in recent_sorted.json()["items"]]
    assert recent_ids.index(newer.json()["id"]) < recent_ids.index(older.json()["id"]) < recent_ids.index(question["id"])

    confidence_sorted = client.get(
        "/api/v1/interview-intelligence/questions",
        params={"company": "Example Co", "track": "CODING", "difficulty": "HARD", "sort": "confidence"},
    )
    assert confidence_sorted.status_code == 200, confidence_sorted.text
    confidence_ids = [row["id"] for row in confidence_sorted.json()["items"]]
    assert confidence_ids.index(newer.json()["id"]) < confidence_ids.index(older.json()["id"]) < confidence_ids.index(question["id"])

    attempt = client.post(
        "/api/v1/interview-intelligence/attempts",
        json={
            "question_id": question["id"],
            "job_id": job_id,
            "answer_text": "I would bound queue capacity, define producer backpressure, coordinate a worker pool, test concurrency invariants, and verify overload behavior.",
        },
    )
    assert attempt.status_code == 201, attempt.text

    progress = client.get("/api/v1/interview-intelligence/progress")
    assert progress.status_code == 200, progress.text
    question_progress = progress.json()["by_question"][question["id"]]
    assert question_progress["attempts"] == 1
    assert question_progress["latest_score"] == attempt.json()["score"]
    assert question_progress["best_score"] == attempt.json()["score"]

    second_attempt = client.post(
        "/api/v1/interview-intelligence/attempts",
        json={
            "question_id": question["id"],
            "job_id": job_id,
            "answer_text": "queue",
        },
    )
    assert second_attempt.status_code == 201, second_attempt.text
    refreshed_progress = client.get("/api/v1/interview-intelligence/progress")
    assert refreshed_progress.status_code == 200, refreshed_progress.text
    refreshed = refreshed_progress.json()["by_question"][question["id"]]
    assert refreshed["attempts"] == 2
    assert refreshed["latest_score"] == second_attempt.json()["score"]
    assert refreshed["best_score"] == max(attempt.json()["score"], second_attempt.json()["score"])



def test_question_bank_filters_before_catalog_cap_and_progress_uses_full_history(client, database_url) -> None:
    _seed(database_url, client)

    app.dependency_overrides[require_operator_or_internal] = lambda: None
    try:
        created = client.post(
            "/api/v1/internal/interview-intelligence/questions",
            json={
                "title": "Low-ranked target question",
                "slug": "review-gap-target-question",
                "track": "CODING",
                "difficulty": "HARD",
                "summary": "Clean-room target question used to prove filtering happens before catalog truncation.",
                "prompt": "Explain how you would design and verify a bounded worker queue under sustained overload.",
                "companies": ["Example Co"],
                "stages": ["SCREENING"],
                "skills": ["concurrency"],
                "patterns": ["queue"],
                "frequency_score": 0,
                "published": True,
            },
        )
        assert created.status_code == 201, created.text
        question_id = created.json()["id"]
    finally:
        app.dependency_overrides.pop(require_operator_or_internal, None)

    engine = create_engine(database_url)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "a@example.com"))
        question = session.get(InterviewIntelligenceQuestion, question_id)
        assert user is not None and question is not None

        session.add_all(
            [
                InterviewIntelligenceQuestion(
                    slug=f"review-gap-distractor-{index}",
                    title=f"High-ranked distractor {index}",
                    track="CODING",
                    difficulty="HARD",
                    summary="Clean-room distractor that must not hide the target from a filtered query.",
                    prompt="Describe a generic coding problem that is not part of the requested company or stage.",
                    baseline_company_labels=["Other Co"],
                    company_labels=["Other Co"],
                    stages=["PHONE"],
                    skills=[],
                    patterns=[],
                    hints=[],
                    follow_ups=[],
                    solution_outline=[],
                    baseline_frequency_score=100,
                    frequency_score=100,
                    confidence=100,
                    report_count=0,
                    published=True,
                )
                for index in range(1001)
            ]
        )

        attempts = []
        for index in range(1001):
            attempts.append(
                InterviewQuestionAttempt(
                    user_id=user.id,
                    question_id=question.id,
                    answer_text="historical practice",
                    status="COMPLETED",
                    score=100 if index == 0 else 10,
                    feedback_json={},
                    created_at=now - timedelta(seconds=1001 - index),
                    updated_at=now - timedelta(seconds=1001 - index),
                )
            )
        session.add_all(attempts)
        session.commit()
    engine.dispose()

    filtered = client.get(
        "/api/v1/interview-intelligence/questions",
        params={
            "company": "example co",
            "stage": "screening",
            "track": "CODING",
            "difficulty": "HARD",
            "limit": 10,
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 1
    assert [item["id"] for item in filtered.json()["items"]] == [question_id]

    progress = client.get("/api/v1/interview-intelligence/progress")
    assert progress.status_code == 200, progress.text
    question_progress = progress.json()["by_question"][question_id]
    assert progress.json()["total_attempts"] == 1001
    assert question_progress == {
        "attempts": 1001,
        "best_score": 100,
        "latest_score": 10,
    }


def test_future_reported_at_is_rejected_before_it_can_skew_freshness(client, database_url) -> None:
    _seed(database_url, client)
    response = client.post(
        "/api/v1/interview-intelligence/reports",
        json={
            "company": "Example Co",
            "role": "Data Architect",
            "interview_stage": "SCREENING",
            "title": "Future-dated report",
            "body": "This report is intentionally future dated and must never influence freshness evidence.",
            "reported_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        },
    )
    assert response.status_code == 422, response.text
    assert "reported_at cannot be in the future" in response.text



def test_question_workspace_submission_history_and_discussion(client, database_url) -> None:
    _seed(database_url, client)

    app.dependency_overrides[require_operator_or_internal] = lambda: None
    try:
        created = client.post(
            "/api/v1/internal/interview-intelligence/questions",
            json={
                "title": "Design a resilient iterator service",
                "slug": "test-question-workspace",
                "track": "CODING",
                "difficulty": "MEDIUM",
                "summary": "Clean-room workspace question used to certify submissions and discussion.",
                "prompt": "Design an iterator-like service and explain correctness, complexity, edge cases, and verification.",
                "companies": ["Example Co"],
                "stages": ["SCREENING"],
                "skills": ["complexity", "testing"],
                "patterns": ["iterator"],
                "hints": ["Define the state and invariants first."],
                "follow_ups": ["How would you make the iterator restartable?"],
                "solution_outline": ["Define state", "Establish invariants", "Analyze complexity", "Test boundaries"],
                "frequency_score": 25,
                "published": True,
            },
        )
        assert created.status_code == 201, created.text
        question = created.json()
    finally:
        app.dependency_overrides.pop(require_operator_or_internal, None)

    first = client.post(
        "/api/v1/interview-intelligence/attempts",
        json={
            "question_id": question["id"],
            "answer_text": "Define iterator state, preserve invariants, handle edge cases, test boundaries, and analyze complexity.",
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/interview-intelligence/attempts",
        json={
            "question_id": question["id"],
            "answer_text": "iterator state",
        },
    )
    assert second.status_code == 201, second.text

    submissions = client.get(
        f"/api/v1/interview-intelligence/questions/{question['slug']}/submissions",
        params={"limit": 1},
    )
    assert submissions.status_code == 200, submissions.text
    submission_payload = submissions.json()
    assert submission_payload["question_id"] == question["id"]
    assert submission_payload["total"] == 2
    assert submission_payload["scored"] == 2
    assert submission_payload["average_score"] is not None
    assert submission_payload["strong_attempts"] in {0, 1, 2}
    assert len(submission_payload["items"]) == 1
    assert submission_payload["items"][0]["score"] == second.json()["score"]
    assert submission_payload["items"][0]["answer_excerpt"] == "iterator state"

    general_post = client.post(
        "/api/v1/interview-intelligence/community",
        json={
            "company": "Example Co",
            "category": "INTERVIEW_EXPERIENCE",
            "title": "General interview note",
            "body": "This is a general candidate community post and is not scoped to a single question.",
        },
    )
    assert general_post.status_code == 201, general_post.text
    assert general_post.json()["question_id"] is None

    discussion_post = client.post(
        "/api/v1/interview-intelligence/community",
        json={
            "question_id": question["id"],
            "company": "Example Co",
            "category": "INTERVIEW_EXPERIENCE",
            "title": "Iterator edge-case discussion",
            "body": "I would explicitly test exhaustion, boundary transitions, and complexity before optimizing the implementation.",
        },
    )
    assert discussion_post.status_code == 201, discussion_post.text
    assert discussion_post.json()["question_id"] == question["id"]

    discussion = client.get(
        "/api/v1/interview-intelligence/community",
        params={"question_id": question["id"]},
    )
    assert discussion.status_code == 200, discussion.text
    assert [item["id"] for item in discussion.json()] == [discussion_post.json()["id"]]
    assert discussion.json()[0]["question_id"] == question["id"]

    missing_question = client.post(
        "/api/v1/interview-intelligence/community",
        json={
            "question_id": "00000000-0000-0000-0000-000000000001",
            "title": "Missing question",
            "body": "This post must be rejected because the referenced interview question does not exist.",
        },
    )
    assert missing_question.status_code == 404, missing_question.text
