from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import EmployerOrganization


def test_candidate_platform_saved_search_notifications_resume_and_analytics(client):
    assert client.get("/api/v1/me").status_code == 200

    saved = client.post(
        "/api/v1/saved-searches",
        json={"name": "AI leadership", "query": {"q": "AI"}, "alerts_enabled": True, "minimum_match_score": 75},
    )
    assert saved.status_code == 201
    assert client.get("/api/v1/saved-searches").json()[0]["name"] == "AI leadership"

    preferences = client.put(
        "/api/v1/notification-preferences",
        json={
            "email_enabled": True,
            "push_enabled": False,
            "job_match_enabled": True,
            "application_reminder_enabled": True,
            "interview_reminder_enabled": True,
            "recruiter_followup_enabled": True,
            "quiet_hours": {"start": "22:00", "end": "07:00"},
        },
    )
    assert preferences.status_code == 200
    assert preferences.json()["push_enabled"] is False

    contact = client.post("/api/v1/contacts", json={"name": "Recruiter A", "company": "Acme"})
    assert contact.status_code == 201

    document = client.post("/api/v1/resume-studio", json={"title": "Leadership Resume", "content": {"summary": "Data and AI leader", "sections": [{"heading": "Experience", "body": ["Led verified programs"]}]}})
    assert document.status_code == 201
    export = client.get(f"/api/v1/resume-studio/{document.json()['id']}/export?format=txt")
    assert export.status_code == 200
    assert "Data and AI leader" in export.json()["content"]

    assert client.post("/api/v1/analytics/events", json={"event_type": "RESUME_EXPORTED", "entity_type": "resume", "entity_id": document.json()["id"]}).status_code == 204
    summary = client.get("/api/v1/analytics/summary")
    assert summary.status_code == 200
    assert summary.json()["resume_documents"] == 1
    assert summary.json()["network_contacts"] == 1
    assert summary.json()["events"]["RESUME_EXPORTED"] == 1


def test_employer_first_party_application_connects_candidate_and_recruiter(client, switch_user, database_url):
    assert client.get("/api/v1/me").status_code == 200
    org = client.post("/api/v1/employer/organizations", json={"name": "ApplyAI Test Employer"})
    assert org.status_code == 201
    org_id = org.json()["id"]

    engine = create_engine(database_url)
    with Session(engine) as session:
        organization = session.scalar(select(EmployerOrganization).where(EmployerOrganization.id == org_id))
        organization.verification_status = "VERIFIED"
        session.commit()
    engine.dispose()

    job = client.post(
        f"/api/v1/employer/organizations/{org_id}/jobs",
        json={
            "title": "Director of Data Engineering",
            "description": "Lead a data engineering organization and build reliable AI-ready platforms.",
            "location_text": "Boston, MA",
            "work_mode": "HYBRID",
            "employment_type": "FULL_TIME",
            "seniority": "DIRECTOR",
            "compensation_min": 220000,
            "compensation_max": 300000,
            "currency": "USD",
        },
    )
    assert job.status_code == 201
    published = client.post(f"/api/v1/employer/jobs/{job.json()['id']}/publish")
    assert published.status_code == 200
    canonical_job_id = published.json()["canonical_job_id"]

    switch_user("clerk_candidate_b", "candidate@example.com")
    assert client.get("/api/v1/me").status_code == 200
    application = client.post("/api/v1/applications", json={"job_id": canonical_job_id})
    assert application.status_code == 201
    submission = client.post("/api/v1/submissions", json={"application_id": application.json()["id"], "mode": "FIRST_PARTY", "provider": "APPLYAI"})
    assert submission.status_code == 201
    approved = client.post(f"/api/v1/submissions/{submission.json()['id']}/approve")
    assert approved.status_code == 200
    executed = client.post(f"/api/v1/submissions/{submission.json()['id']}/execute")
    assert executed.status_code == 200
    assert executed.json()["submitted"] is True

    switch_user("clerk_user_a", "a@example.com")
    applicants = client.get(f"/api/v1/employer/jobs/{job.json()['id']}/applicants")
    assert applicants.status_code == 200
    assert len(applicants.json()) == 1
    assert applicants.json()[0]["candidate_email"] == "candidate@example.com"


def test_billing_entitlements_default_to_free(client):
    assert client.get("/api/v1/me").status_code == 200
    subscription = client.get("/api/v1/billing/subscription")
    assert subscription.status_code == 200
    assert subscription.json()["plan"] == "FREE"
    assert subscription.json()["entitlements"]["job_alerts"] is True
