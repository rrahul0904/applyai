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
            }
        ],
        "education": [],
        "skills": [
            {"name": "Python", "provenance": "USER_VERIFIED"},
            {"name": "SQL", "provenance": "USER_VERIFIED"},
            {"name": "Machine learning", "provenance": "USER_VERIFIED"},
            {"name": "Analytics", "provenance": "USER_VERIFIED"},
        ],
    }


def test_workspace_recommendations_and_tailoring_persist(client):
    seed_jobs()
    profile_response = client.put("/api/v1/profile", json=profile_payload())
    assert profile_response.status_code == 200

    recommendation_response = client.get(
        "/api/v1/workspace/recommendations?limit=10"
    )
    assert recommendation_response.status_code == 200
    recommendation_payload = recommendation_response.json()
    assert recommendation_payload["profile_ready"] is True
    assert len(recommendation_payload["items"]) >= 3
    scores = [item["match_score"] for item in recommendation_payload["items"]]
    assert scores == sorted(scores, reverse=True)
    assert all(item["strengths"] for item in recommendation_payload["items"])
    assert all(item["gaps"] for item in recommendation_payload["items"])

    job_id = recommendation_payload["items"][0]["id"]
    tailoring_response = client.get(f"/api/v1/workspace/tailoring/{job_id}")
    assert tailoring_response.status_code == 200
    tailoring = tailoring_response.json()
    assert tailoring["application_id"] is None
    assert len(tailoring["edits"]) == 3
    assert all(edit["decision"] == "PENDING" for edit in tailoring["edits"])

    edits = [
        {
            "index": edit["index"],
            "text": edit["text"],
            "decision": "APPROVED" if edit["index"] == 0 else "REJECTED",
        }
        for edit in tailoring["edits"]
    ]
    save_response = client.put(
        f"/api/v1/workspace/tailoring/{job_id}",
        json={"edits": edits},
    )
    assert save_response.status_code == 200
    saved_tailoring = save_response.json()
    assert saved_tailoring["application_id"] is not None
    assert saved_tailoring["edits"][0]["decision"] == "APPROVED"
    assert saved_tailoring["edits"][1]["decision"] == "REJECTED"

    applications_response = client.get("/api/v1/applications")
    assert applications_response.status_code == 200
    applications = applications_response.json()["items"]
    assert len(applications) == 1
    assert applications[0]["job_id"] == job_id
    assert applications[0]["current_status"] == "PREPARING"

    saved_jobs_response = client.get("/api/v1/jobs/saved")
    assert saved_jobs_response.status_code == 200
    saved_jobs = saved_jobs_response.json()["items"]
    assert len(saved_jobs) == 1
    assert saved_jobs[0]["id"] == job_id

    reload_response = client.get(f"/api/v1/workspace/tailoring/{job_id}")
    assert reload_response.status_code == 200
    reloaded = reload_response.json()
    assert reloaded["application_id"] == saved_tailoring["application_id"]
    assert [edit["decision"] for edit in reloaded["edits"]] == [
        "APPROVED",
        "REJECTED",
        "REJECTED",
    ]
