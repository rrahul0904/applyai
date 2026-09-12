from datetime import datetime, timedelta, timezone

from app.interview_intelligence_service import (
    evidence_confidence,
    freshness_score,
    personalized_plan,
    report_fingerprint,
    slugify,
    staged_hint,
)


def test_slugify_is_stable():
    assert slugify("ML System Design / Feature Store") == "ml-system-design-feature-store"


def test_report_fingerprint_normalizes_whitespace_and_case():
    first = report_fingerprint(source_type="USER_SUBMISSION", source_url=None, company="OpenAI", role="Platform Engineer", body="Rate   limiting round")
    second = report_fingerprint(source_type="user_submission", source_url=None, company="openai", role="platform engineer", body="rate limiting round")
    assert first == second


def test_evidence_confidence_requires_moderation_and_is_bounded():
    assert evidence_confidence(independent_reports=10, source_diversity=5, age_days=0, moderation_approved=False) == 0
    assert evidence_confidence(independent_reports=10, source_diversity=5, age_days=0, moderation_approved=True) == 100


def test_freshness_score_decays_with_age():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    recent = freshness_score(now - timedelta(days=3), now=now)
    old = freshness_score(now - timedelta(days=180), now=now)
    assert recent > old
    assert 0 <= old <= recent <= 100


def test_personalized_plan_prioritizes_gaps_and_tracks():
    plan = personalized_plan(job_title="Senior Data Engineer", candidate_skills=["python", "sql"], required_skills=["python", "sql", "spark", "system design"], question_tracks={"CODING": 12, "SQL": 6, "SYSTEM_DESIGN": 9})
    assert plan["readiness_score"] < 95
    assert plan["strengths"] == ["python", "sql"]
    assert plan["gaps"] == ["spark", "system design"]
    assert plan["actions"][0]["track"] == "SKILL_GAP"
    assert {item["track"] for item in plan["actions"][1:]} >= {"CODING", "SQL", "SYSTEM_DESIGN"}


def test_staged_hint_never_leaks_beyond_available_hints():
    response = staged_hint(hints=["First", "Second"], requested_level=9, answer="x" * 50)
    assert response["level"] == 1
    assert response["next_level"] == 1
    assert "Second" in response["hint"]
