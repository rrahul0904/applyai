from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs


def seed_jobs() -> None:
    with SessionLocal() as session:
        seed_development_jobs(session)


def candidate_profile() -> dict:
    return {
        "headline": "Senior data engineering leader",
        "current_title": "Senior Data Engineering Manager",
        "summary": (
            "Data platform leader with 12 years of experience building reliable "
            "analytics and machine-learning infrastructure."
        ),
        "years_experience": 12,
        "target_roles": [
            "Data Engineering Manager",
            "Analytics Engineering Manager",
            "Machine Learning Engineering Manager",
        ],
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
            },
            {
                "company_name": "Summit Commerce",
                "title": "Data Platform Lead",
                "start_date": "2017-01-01",
                "end_date": "2020-12-31",
                "description": (
                    "Modernized AWS and Snowflake data platforms and introduced "
                    "shared analytics engineering standards."
                ),
                "provenance": "USER_VERIFIED",
            },
        ],
        "education": [],
        "skills": [
            {"name": "Python", "provenance": "USER_VERIFIED"},
            {"name": "SQL", "provenance": "USER_VERIFIED"},
            {"name": "Analytics", "provenance": "USER_VERIFIED"},
            {"name": "Machine learning", "provenance": "USER_VERIFIED"},
            {"name": "AWS", "provenance": "USER_VERIFIED"},
            {"name": "Snowflake", "provenance": "USER_VERIFIED"},
        ],
    }


def test_explainable_match_tailoring_and_application_assistant(client):
    seed_jobs()
    profile_response = client.put("/api/v1/profile", json=candidate_profile())
    assert profile_response.status_code == 200

    matches_response = client.get("/api/v1/career-v1/matches?limit=12")
    assert matches_response.status_code == 200
    matches = matches_response.json()
    assert matches["engine_version"] == "applyai-explainable-fit-v1"
    assert len(matches["items"]) >= 3
    scores = [item["match_score"] for item in matches["items"]]
    assert scores == sorted(scores, reverse=True)
    assert all(len(item["breakdown"]) == 6 for item in matches["items"])
    assert all(item["confidence"] in {"LOW", "MEDIUM", "HIGH"} for item in matches["items"])
    assert all(item["decision"] in {"PRIORITIZE", "CONSIDER", "STRETCH", "SKIP"} for item in matches["items"])

    selected = next(item for item in matches["items"] if item["match_score"] >= 60)
    job_id = selected["job_id"]
    detail_response = client.get(f"/api/v1/career-v1/matches/{job_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert sum(item["score"] for item in detail["breakdown"]) == detail["match_score"]
    assert "hiring probability" not in detail["summary"].lower()

    tailoring_response = client.get(f"/api/v1/career-v1/tailoring/{job_id}")
    assert tailoring_response.status_code == 200
    tailoring = tailoring_response.json()
    assert tailoring["safety"]["policy"] == "EVIDENCE_LOCKED"
    assert tailoring["application_id"] is None
    assert len(tailoring["edits"]) == 3

    save_tailoring_response = client.put(
        f"/api/v1/career-v1/tailoring/{job_id}",
        json={
            "edits": [
                {
                    "index": edit["index"],
                    "text": edit["text"],
                    "decision": "APPROVED" if edit["index"] in {0, 1} else "REJECTED",
                }
                for edit in tailoring["edits"]
            ]
        },
    )
    assert save_tailoring_response.status_code == 200
    assert save_tailoring_response.json()["application_id"] is not None

    finalize_resume_response = client.post(
        f"/api/v1/career-v1/tailoring/{job_id}/finalize"
    )
    assert finalize_resume_response.status_code == 200
    finalized_resume = finalize_resume_response.json()
    assert finalized_resume["status"] == "FINALIZED"
    assert finalized_resume["approved_edits"] == 2
    assert "Approved targeted language" in finalized_resume["tailored_resume_markdown"]

    assistant_response = client.get(
        f"/api/v1/career-v1/application-assistant/{job_id}"
    )
    assert assistant_response.status_code == 200
    assistant = assistant_response.json()
    assert assistant["readiness_score"] == 65
    assert assistant["external_submission_required"] is True
    assert len(assistant["questions"]) == 3
    assert assistant["ready_to_finalize"] is False

    save_assistant_response = client.put(
        f"/api/v1/career-v1/application-assistant/{job_id}",
        json={
            "cover_letter": assistant["cover_letter"],
            "cover_letter_verified": True,
            "answers": [
                {
                    "question": item["question"],
                    "answer": item["answer"],
                    "user_verified": True,
                }
                for item in assistant["questions"]
            ],
        },
    )
    assert save_assistant_response.status_code == 200
    saved_assistant = save_assistant_response.json()
    assert saved_assistant["readiness_score"] == 100
    assert saved_assistant["ready_to_finalize"] is True

    finalize_package_response = client.post(
        f"/api/v1/career-v1/application-assistant/{job_id}/finalize"
    )
    assert finalize_package_response.status_code == 200
    package = finalize_package_response.json()
    assert package["current_status"] == "READY"
    assert package["readiness_score"] == 100
    assert package["external_submission_required"] is True

    applications_response = client.get("/api/v1/applications")
    assert applications_response.status_code == 200
    application = applications_response.json()["items"][0]
    assert application["job_id"] == job_id
    assert application["current_status"] == "READY"

    reload_response = client.get(
        f"/api/v1/career-v1/application-assistant/{job_id}"
    )
    assert reload_response.status_code == 200
    reloaded = reload_response.json()
    assert reloaded["readiness_score"] == 100
    assert reloaded["cover_letter_verified"] is True
    assert all(item["user_verified"] for item in reloaded["questions"])
