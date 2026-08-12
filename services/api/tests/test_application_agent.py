from sqlalchemy import select

from app.application_agent_models import ApplicationExecution, ApplicationQuestionMemory
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs
from app.main import app
from app.models import Application, ApplicationEvent


def _profile() -> dict:
    return {
        "headline": "Clinical research coordinator",
        "current_title": "Clinical Research Coordinator",
        "summary": "Coordinates participant-facing research and regulated study operations.",
        "years_experience": 5,
        "target_roles": ["Clinical Research Coordinator"],
        "location_text": "Boston, MA",
        "work_modes": ["ONSITE", "HYBRID"],
        "minimum_compensation": 65000,
        "experiences": [
            {
                "company_name": "Verified Research Center",
                "title": "Clinical Research Coordinator",
                "start_date": "2022-01-01",
                "end_date": None,
                "description": "Coordinated recruitment, study visits, source documentation, and regulatory workflows.",
                "provenance": "USER_VERIFIED",
            }
        ],
        "education": [],
        "skills": [
            {"name": "Clinical trials", "provenance": "USER_VERIFIED"},
            {"name": "GCP", "provenance": "USER_VERIFIED"},
            {"name": "Regulatory documentation", "provenance": "USER_VERIFIED"},
        ],
    }


def _selected_job(client) -> str:
    matches = client.get("/api/v1/career-v1/matches?limit=10")
    assert matches.status_code == 200
    return str(matches.json()["items"][0]["job_id"])


def _prepare_copilot(client, job_id: str) -> str:
    resume = client.post(f"/api/v1/career-v2/jobs/{job_id}/resume-tailoring")
    assert resume.status_code == 200
    assert resume.json()["status"] == "COMPLETED"
    copilot = client.post(f"/api/v1/career-v2/jobs/{job_id}/application-copilot")
    assert copilot.status_code == 200
    assert copilot.json()["status"] == "COMPLETED"
    return str(copilot.json()["application_id"])


def test_application_agent_reuses_verified_answers_and_requires_confirmation(client):
    with SessionLocal() as session:
        seed_development_jobs(session)
    assert client.put("/api/v1/profile", json=_profile()).status_code == 200
    job_id = _selected_job(client)
    application_id = _prepare_copilot(client, job_id)

    memory = client.put(
        "/api/v1/application-agent/memory/sponsorship",
        json={
            "canonical_key": "sponsorship",
            "question": "Will you now or in the future require sponsorship?",
            "answer": "No",
            "answer_type": "SELECT",
            "sensitive": True,
            "candidate_verified": True,
        },
    )
    assert memory.status_code == 200
    assert memory.json()["candidate_verified"] is True

    prepared = client.post(
        f"/api/v1/application-agent/applications/{application_id}/prepare",
        json={
            "approval_mode": "SMART",
            "observed_fields": [
                {"field_id": "first_name", "label": "First name", "field_type": "TEXT", "required": True},
                {"field_id": "email", "label": "Email", "field_type": "TEXT", "required": True},
                {
                    "field_id": "sponsorship",
                    "label": "Do you require visa sponsorship?",
                    "field_type": "SELECT",
                    "required": True,
                    "options": ["Yes", "No"],
                },
            ],
        },
    )
    assert prepared.status_code == 201
    payload = prepared.json()
    assert payload["state"] == "READY_FOR_APPROVAL"
    assert payload["missing_fields"] == []
    assert payload["review_items"] == []
    sponsorship = next(item for item in payload["fields"] if item["canonical_key"] == "sponsorship")
    assert sponsorship["value"] == "No"
    assert sponsorship["source_kind"] == "ANSWER_MEMORY"
    assert sponsorship["candidate_verified"] is True

    approved = client.post(f"/api/v1/application-agent/executions/{payload['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["state"] == "READY_FOR_EXECUTION"

    queued = client.post(f"/api/v1/application-agent/executions/{payload['id']}/execute")
    assert queued.status_code == 200
    assert queued.json()["state"] == "BROWSER_QUEUED"
    assert queued.json()["browser_handoff"]["captcha_policy"] == "HUMAN_ACTION_REQUIRED"
    assert queued.json()["browser_handoff"]["success_policy"] == "CONFIRMATION_REQUIRED"

    settings = get_settings().model_copy(update={"internal_api_token": "application-agent-test-token"})
    app.dependency_overrides[get_settings] = lambda: settings
    headers = {"X-ApplyAI-Internal-Token": "application-agent-test-token"}
    claimed = client.get("/api/v1/internal/application-agent/executions/next", headers=headers)
    assert claimed.status_code == 200
    assert claimed.json()["execution"]["id"] == payload["id"]

    completed = client.post(
        f"/api/v1/internal/application-agent/executions/{payload['id']}/complete",
        headers=headers,
        json={
            "status": "CONFIRMED",
            "field_results": [{"field_id": "email", "status": "FILLED"}],
            "validation": {"confirmation_signal": "thank you for applying"},
            "confirmation_url": "https://jobs.applyai.test/confirmation/123",
            "confirmation_text": "Thank you for applying. We received your application.",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["state"] == "CONFIRMED"

    with SessionLocal() as session:
        application = session.get(Application, application_id)
        assert application is not None
        assert application.current_status == "APPLIED"
        execution = session.scalar(select(ApplicationExecution).where(ApplicationExecution.application_id == application.id))
        assert execution is not None
        assert execution.confirmed_at is not None
        event = session.scalar(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id, ApplicationEvent.to_status == "APPLIED")
            .order_by(ApplicationEvent.created_at.desc())
        )
        assert event is not None
        assert event.metadata_json["channel"] == "APPLYAI_BROWSER_AGENT"
        answer = session.scalar(
            select(ApplicationQuestionMemory).where(
                ApplicationQuestionMemory.user_id == application.user_id,
                ApplicationQuestionMemory.canonical_key == "sponsorship",
            )
        )
        assert answer is not None
        assert answer.answer == "No"


def test_application_agent_blocks_unknown_required_and_sensitive_answers(client):
    with SessionLocal() as session:
        seed_development_jobs(session)
    assert client.put("/api/v1/profile", json=_profile()).status_code == 200
    job_id = _selected_job(client)
    application_id = _prepare_copilot(client, job_id)

    prepared = client.post(
        f"/api/v1/application-agent/applications/{application_id}/prepare",
        json={
            "approval_mode": "SMART",
            "observed_fields": [
                {
                    "field_id": "oncology_years",
                    "label": "How many years of oncology experience do you have?",
                    "field_type": "TEXT",
                    "required": True,
                },
                {
                    "field_id": "salary",
                    "label": "What are your salary expectations?",
                    "field_type": "TEXT",
                    "required": True,
                },
            ],
        },
    )
    assert prepared.status_code == 201
    payload = prepared.json()
    assert payload["state"] in {"NEEDS_INPUT", "REVIEW_REQUIRED"}
    assert any(item["field_id"] == "oncology_years" for item in payload["missing_fields"])
    assert any(item["field_id"] == "salary" for item in payload["review_items"])

    blocked = client.post(f"/api/v1/application-agent/executions/{payload['id']}/approve")
    assert blocked.status_code == 409

    oncology = client.patch(
        f"/api/v1/application-agent/executions/{payload['id']}/fields/oncology_years",
        json={"value": "0", "candidate_verified": True, "remember": False},
    )
    assert oncology.status_code == 200
    salary = client.patch(
        f"/api/v1/application-agent/executions/{payload['id']}/fields/salary",
        json={"value": "65000", "candidate_verified": True, "remember": True},
    )
    assert salary.status_code == 200
    assert salary.json()["state"] == "READY_FOR_APPROVAL"

    approved = client.post(f"/api/v1/application-agent/executions/{payload['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["state"] == "READY_FOR_EXECUTION"
