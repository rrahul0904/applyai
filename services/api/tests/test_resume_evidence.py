from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.resume_evidence import composition_review, select_verified_facts, unsupported_numeric_claims
from app.career_memory_models import CandidateCareerFact
from app.models import User
from tests.helpers import create_job
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_verified_facts_use_stable_jd_overlap_and_exclude_archived_or_unverified():
    facts = [
        SimpleNamespace(id="b", title="Data pipelines", fact_text="Built Python SQL pipelines", tags=["analytics"], user_verified=True, archived_at=None, occurred_at=date(2025, 1, 1)),
        SimpleNamespace(id="a", title="Other", fact_text="Led retail team", tags=[], user_verified=True, archived_at=None, occurred_at=date(2025, 1, 1)),
        SimpleNamespace(id="c", title="Python SQL", fact_text="Strong claim", tags=[], user_verified=False, archived_at=None, occurred_at=date(2026, 1, 1)),
        SimpleNamespace(id="d", title="Python", fact_text="Old", tags=[], user_verified=True, archived_at=datetime.now(timezone.utc), occurred_at=date(2026, 1, 1)),
    ]
    selected = select_verified_facts("Python SQL data pipelines", facts)
    assert [fact.id for fact, _ in selected] == ["b", "a"]
    assert selected[0][1] > selected[1][1]


def test_numeric_claims_must_exist_in_source_evidence():
    assert unsupported_numeric_claims("Improved throughput by 30% across 4 teams", ["Improved throughput by 30% across 4 teams"]) == []
    assert unsupported_numeric_claims("Improved throughput by 31% across 4 teams", ["Improved throughput by 30% across 4 teams"]) == ["31%"]


def test_composition_signals_overflow_and_plaintext_extractability_without_truncation():
    text = "A verified fact\n" * 300
    review = composition_review(text)
    assert review.page_status == "OVERFLOW_REQUIRES_REVIEW"
    assert review.extractable_text is True
    assert review.characters == len(text)
    assert review.universal_ats_claim is False
    assert composition_review("\x00").extractable_text is False


def test_resume_studio_job_link_locks_source_facts_and_invalidates_revisions(client, database_url):
    assert client.get("/api/v1/me").status_code == 200
    engine = create_engine(database_url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "a@example.com"))
        assert user is not None
        job = create_job(session)
        job.title = "Data Platform Engineer"
        job.description = "Python SQL platform engineering data pipelines and reliability"
        fact = CandidateCareerFact(user_id=user.id, category="ACHIEVEMENT", title="Latency", fact_text="Improved Python SQL query latency by 30%.", source_kind="USER", source_ref="career-memory:fact-1", provenance="USER_VERIFIED", user_verified=True, tags=["Python", "SQL"])
        session.add(fact)
        session.commit()
        job_id, fact_id = str(job.id), fact.id
    engine.dispose()

    created = client.post(f"/api/v1/resume-studio/from-job/{job_id}")
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["job_id"] == job_id
    content = document["content"]
    assert content["evidence_lock"]["enabled"] is True
    assert content["evidence"][0]["id"] == str(fact_id)
    content["summary"] = "Improved query latency by 30%."
    content["sections"] = [{"heading": "Experience", "body": ["Improved query latency by 30%."]}]
    updated = client.put(f"/api/v1/resume-studio/{document['id']}", json={"content": content})
    assert updated.status_code == 200, updated.text

    fabricated = dict(content)
    fabricated["summary"] = "Improved query latency by 300%."
    rejected = client.put(f"/api/v1/resume-studio/{document['id']}", json={"content": fabricated})
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "UNSUPPORTED_NUMERIC_CLAIMS"

    engine = create_engine(database_url)
    with Session(engine) as session:
        fact = session.get(CandidateCareerFact, fact_id)
        fact.fact_text = "Improved Python SQL query latency by 25%."
        session.commit()
    engine.dispose()
    stale = client.put(f"/api/v1/resume-studio/{document['id']}", json={"content": content})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "SOURCE_FACT_REVISION_INVALIDATED"
    revised = client.get(f"/api/v1/resume-studio/{document['id']}")
    assert revised.json()["content"]["revision_invalidated"] is True
