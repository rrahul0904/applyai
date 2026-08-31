from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs


def seed_jobs() -> None:
    with SessionLocal() as session:
        seed_development_jobs(session)


def candidate_profile() -> dict:
    return {
        "headline": "Senior data engineering leader",
        "current_title": "Senior Data Engineering Manager",
        "summary": "Verified data platform leader focused on reliable analytics infrastructure.",
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
                "description": (
                    "Led a verified 12-person data engineering organization using Python, SQL, "
                    "and AWS and reduced pipeline delivery time by 35%."
                ),
                "provenance": "USER_VERIFIED",
            }
        ],
        "education": [],
        "skills": [
            {"name": "Python", "provenance": "USER_VERIFIED"},
            {"name": "SQL", "provenance": "USER_VERIFIED"},
            {"name": "AWS", "provenance": "USER_VERIFIED"},
        ],
    }


def test_recruiter_lens_is_deterministic_and_evidence_bound(client):
    seed_jobs()
    assert client.put("/api/v1/profile", json=candidate_profile()).status_code == 200
    selected = client.get("/api/v1/career-v1/matches?limit=10").json()["items"][0]
    job_id = selected["job_id"]

    first = client.get(f"/api/v1/recruiter-lens/jobs/{job_id}")
    second = client.get(f"/api/v1/recruiter-lens/jobs/{job_id}")
    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()

    assert payload == second.json()
    assert 0 <= payload["score"] <= 100
    assert payload["tier"] in {"A", "B", "C", "D"}
    assert payload["confidence"] in {"HIGH", "MEDIUM", "LOW"}
    assert payload["criteria_source"] == "STRUCTURED_JOB_POSTING"
    assert payload["criteria"]
    assert len(payload["criteria"]) <= 12
    assert payload["engine_version"] == "applyai-recruiter-lens-v1"
    assert payload["policy"]["candidate_self_assessment"] is True
    assert payload["policy"]["employer_prediction"] is False
    assert payload["policy"]["identity_fields_used"] is False
    assert "not an employer score" in payload["disclaimer"].lower()

    supported = [item for item in payload["criteria"] if item["status"] == "SUPPORTED"]
    for item in supported:
        assert item["evidence"] is not None
        assert item["evidence"]["snippet"]

    counts = payload["counts"]
    assert counts["supported"] + counts["partial"] + counts["not_evidenced"] == len(
        payload["criteria"]
    )


def test_recruiter_lens_turns_gaps_into_concerns_and_questions(client):
    seed_jobs()
    sparse_profile = candidate_profile()
    sparse_profile["skills"] = [{"name": "SQL", "provenance": "USER_VERIFIED"}]
    sparse_profile["summary"] = "Verified analytics engineering leader."
    sparse_profile["experiences"][0]["description"] = (
        "Led a verified data engineering team and improved delivery reliability."
    )
    assert client.put("/api/v1/profile", json=sparse_profile).status_code == 200

    selected = client.get("/api/v1/career-v1/matches?limit=10").json()["items"][0]
    payload = client.get(
        f"/api/v1/recruiter-lens/jobs/{selected['job_id']}"
    ).json()

    gaps = [
        item for item in payload["criteria"] if item["status"] != "SUPPORTED"
    ]
    if gaps:
        assert payload["concerns"]
        assert payload["interview_questions"]
        assert any(
            gap["label"] in concern["message"]
            for gap in gaps
            for concern in payload["concerns"]
        )
        assert all(
            "overstating" in item["question"].lower()
            or "specific role" in item["question"].lower()
            for item in payload["interview_questions"]
        )
