from app.core.config import get_settings
from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs
from app.main import app


def profile_payload() -> dict:
    return {
        "headline": "Senior data engineering leader",
        "current_title": "Senior Data Engineering Manager",
        "summary": "Data platform leader with verified experience building reliable analytics infrastructure.",
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
                "description": "Built and led a data engineering organization. Reduced verified pipeline delivery time by 35%.",
                "provenance": "USER_VERIFIED",
            }
        ],
        "education": [
            {
                "institution": "Example University",
                "degree": "Master of Science",
                "field_of_study": "Computer Science",
                "start_date": "2010-09-01",
                "end_date": "2012-05-01",
                "provenance": "USER_VERIFIED",
            }
        ],
        "skills": [
            {"name": "Python", "provenance": "USER_VERIFIED"},
            {"name": "SQL", "provenance": "USER_VERIFIED"},
            {"name": "AWS", "provenance": "USER_VERIFIED"},
        ],
    }


def selected_job(client) -> str:
    matches = client.get("/api/v1/career-v1/matches?limit=10")
    assert matches.status_code == 200
    return str(matches.json()["items"][0]["job_id"])


def prepare_execution(client, job_id: str) -> dict:
    resume = client.post(f"/api/v1/career-v2/jobs/{job_id}/resume-tailoring")
    assert resume.status_code == 200
    copilot = client.post(f"/api/v1/career-v2/jobs/{job_id}/application-copilot")
    assert copilot.status_code == 200
    application_id = str(copilot.json()["application_id"])
    prepared = client.post(
        f"/api/v1/application-agent/applications/{application_id}/prepare",
        json={"approval_mode": "SMART", "observed_fields": []},
    )
    assert prepared.status_code == 201
    return prepared.json()


def test_application_documents_are_private_generated_and_candidate_gated(client):
    with SessionLocal() as session:
        seed_development_jobs(session)
    assert client.put("/api/v1/profile", json=profile_payload()).status_code == 200
    execution = prepare_execution(client, selected_job(client))

    generated = client.post(
        f"/api/v1/application-agent/executions/{execution['id']}/documents/generate"
    )
    assert generated.status_code == 200
    documents = generated.json()["documents"]
    assert documents["resume"]["candidate_verified"] is True
    assert documents["resume"]["storage_key"].startswith("candidate/")
    assert documents["resume"]["truth_policy"] == "CANONICAL_PROFILE_PLUS_CANDIDATE_APPROVED_REVISIONS"
    assert documents["resume"]["filename"].endswith(".docx")
    assert documents["cover_letter"]["storage_key"].startswith("candidate/")
    assert documents["cover_letter"]["candidate_verified"] is False

    settings = get_settings().model_copy(update={"internal_api_token": "application-doc-test-token"})
    app.dependency_overrides[get_settings] = lambda: settings
    headers = {"X-ApplyAI-Internal-Token": "application-doc-test-token"}

    resume_download = client.get(
        f"/api/v1/internal/application-agent/executions/{execution['id']}/documents/resume",
        headers=headers,
    )
    assert resume_download.status_code == 200
    assert resume_download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert resume_download.content.startswith(b"PK")

    cover_blocked = client.get(
        f"/api/v1/internal/application-agent/executions/{execution['id']}/documents/cover_letter",
        headers=headers,
    )
    assert cover_blocked.status_code == 409

    approve_cover = client.patch(
        f"/api/v1/application-agent/executions/{execution['id']}/documents/cover_letter",
        json={"candidate_verified": True},
    )
    assert approve_cover.status_code == 200
    assert approve_cover.json()["documents"]["cover_letter"]["candidate_verified"] is True

    cover_download = client.get(
        f"/api/v1/internal/application-agent/executions/{execution['id']}/documents/cover_letter",
        headers=headers,
    )
    assert cover_download.status_code == 200
    assert cover_download.content.startswith(b"PK")
