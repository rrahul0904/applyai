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
                "description": "Led a verified 12-person data engineering organization and reduced pipeline delivery time by 35%.",
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


def test_career_system_composes_existing_applyai_workflows(client):
    seed_jobs()
    profile_response = client.put("/api/v1/profile", json=candidate_profile())
    assert profile_response.status_code == 200

    matches = client.get("/api/v1/career-v1/matches?limit=10").json()["items"]
    selected = next(item for item in matches if item["match_score"] >= 50)
    job_id = selected["job_id"]

    response = client.get(f"/api/v1/career-system/jobs/{job_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["job_id"] == job_id
    assert payload["application_id"] is None
    assert payload["match"]["match_score"] == selected["match_score"]
    assert "not a hiring probability" in payload["progress_explanation"].lower()
    assert [stage["id"] for stage in payload["stages"]] == [
        "profile",
        "resume",
        "fit",
        "package",
        "outreach",
        "interview",
        "application",
    ]
    assert payload["safety"]["evidence_policy"] == "VERIFIED_EVIDENCE_ONLY"
    assert payload["portfolio_preview"]["headline"] == "Senior data engineering leader"
    assert "Verified data platform leader" in payload["portfolio_preview"]["about"]
    assert payload["portfolio_preview"]["highlights"][0]["company"] == "Atlas Health"
    assert "Python" in payload["portfolio_preview"]["skills"]
    assert payload["interview"]["ready"] is False
    assert payload["interview"]["status"] == "NOT_STARTED"
    assert payload["interview"]["starter_questions"]
    assert payload["communications"]["recruiter_message_verified"] is False
    assert payload["communications"]["follow_up_message_verified"] is False
    assert selected["title"] in payload["communications"]["recruiter_message"]


def test_career_system_persists_candidate_reviewed_communications(client):
    seed_jobs()
    assert client.put("/api/v1/profile", json=candidate_profile()).status_code == 200
    selected = client.get("/api/v1/career-v1/matches?limit=10").json()["items"][0]
    job_id = selected["job_id"]

    before = client.get(f"/api/v1/career-system/jobs/{job_id}").json()
    progress_before = before["progress_score"]
    recruiter_message = before["communications"]["recruiter_message"] + " Happy to share more context."
    follow_up_message = before["communications"]["follow_up_message"] + " I appreciate your consideration."

    saved_response = client.put(
        f"/api/v1/career-system/jobs/{job_id}/communications",
        json={
            "recruiter_message": recruiter_message,
            "recruiter_message_verified": True,
            "follow_up_message": follow_up_message,
            "follow_up_message_verified": True,
        },
    )
    assert saved_response.status_code == 200
    saved = saved_response.json()
    assert saved["application_id"] is not None
    assert saved["communications"]["recruiter_message"] == recruiter_message
    assert saved["communications"]["follow_up_message"] == follow_up_message
    assert saved["communications"]["recruiter_message_verified"] is True
    assert saved["communications"]["follow_up_message_verified"] is True
    assert saved["progress_score"] >= progress_before + 20

    reloaded = client.get(f"/api/v1/career-system/jobs/{job_id}")
    assert reloaded.status_code == 200
    payload = reloaded.json()
    assert payload["communications"]["recruiter_message"] == recruiter_message
    assert payload["communications"]["follow_up_message"] == follow_up_message
    assert payload["communications"]["policy"] == "CANDIDATE_REVIEW_REQUIRED"
