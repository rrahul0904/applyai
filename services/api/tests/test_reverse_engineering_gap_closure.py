from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.jobs.seed import seed_development_jobs
from tests.test_resume_share_intelligence import _seed_resume_and_job


def _seed_jobs() -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        seed_development_jobs(session)


def test_portfolio_is_opt_in_public_and_owner_scoped(client, switch_user):
    assert client.get("/api/v1/me").status_code == 200

    initial = client.get("/api/v1/growth/portfolio")
    assert initial.status_code == 200
    assert initial.json()["published"] is False

    configured = client.put(
        "/api/v1/growth/portfolio",
        json={
            "slug": "candidate-a-portfolio",
            "published": False,
            "theme": "TECHNICAL",
            "indexing_allowed": False,
            "headline": "Data platform leader",
            "about": "Evidence-backed career portfolio.",
            "visibility": {"experience": True, "education": False, "skills": True},
            "contact_enabled": False,
        },
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["published"] is False
    assert (
        client.get("/api/v1/growth/public/portfolio/candidate-a-portfolio").status_code
        == 404
    )

    project = client.post(
        "/api/v1/growth/portfolio/projects",
        json={
            "title": "Verified migration",
            "summary": "Migrated a verified data platform workload.",
            "role": "Technical lead",
            "technologies": ["Python", "SQL"],
            "verified_outcome": "Reduced a verified batch window by 20%.",
            "project_url": "https://example.com/project",
            "visible": True,
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    published = client.put(
        "/api/v1/growth/portfolio",
        json={
            "slug": "candidate-a-portfolio",
            "published": True,
            "theme": "TECHNICAL",
            "indexing_allowed": False,
            "headline": "Data platform leader",
            "about": "Evidence-backed career portfolio.",
            "visibility": {
                "headline": True,
                "about": True,
                "experience": True,
                "education": False,
                "skills": True,
                "projects": True,
                "resume": False,
                "contact_links": False,
            },
            "contact_enabled": False,
        },
    )
    assert published.status_code == 200

    public = client.get("/api/v1/growth/public/portfolio/candidate-a-portfolio")
    assert public.status_code == 200
    payload = public.json()
    assert payload["slug"] == "candidate-a-portfolio"
    assert payload["privacy"]["candidate_opt_in"] is True
    assert payload["privacy"]["raw_resume_exposed"] is False
    assert payload["education"] == []
    assert payload["projects"][0]["title"] == "Verified migration"

    switch_user("clerk_user_b", "b@example.com")
    assert client.get("/api/v1/growth/portfolio/projects").json() == []
    forbidden_update = client.put(
        f"/api/v1/growth/portfolio/projects/{project_id}",
        json={
            "title": "Hijacked",
            "summary": "Should not be writable by another user.",
            "technologies": [],
            "visible": True,
        },
    )
    assert forbidden_update.status_code == 404
    assert client.delete(f"/api/v1/growth/portfolio/projects/{project_id}").status_code == 404


def test_recruiter_lens_criteria_block_protected_fields_and_are_owner_scoped(client, switch_user):
    assert client.get("/api/v1/me").status_code == 200

    blocked = client.post(
        "/api/v1/growth/recruiter-lens/criteria-sets",
        json={
            "name": "Unsafe",
            "mode": "CUSTOM",
            "criteria": [{"label": "Candidate age under 40", "required": True, "weight": 1.0}],
        },
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "PROTECTED_CRITERION_BLOCKED"

    created = client.post(
        "/api/v1/growth/recruiter-lens/criteria-sets",
        json={
            "name": "Strict technical",
            "mode": "TECHNICAL",
            "criteria": [
                {"label": "Python production experience", "required": True, "weight": 2.0},
                {"label": "SQL query design", "required": True, "weight": 1.5},
            ],
        },
    )
    assert created.status_code == 201, created.text
    set_id = created.json()["id"]

    switch_user("clerk_user_b", "b@example.com")
    assert client.get("/api/v1/growth/recruiter-lens/criteria-sets").json() == []
    update = client.put(
        f"/api/v1/growth/recruiter-lens/criteria-sets/{set_id}",
        json={
            "name": "Should fail",
            "mode": "CUSTOM",
            "criteria": [{"label": "Python", "required": True, "weight": 1.0}],
        },
    )
    assert update.status_code == 404
    assert (
        client.post(f"/api/v1/growth/recruiter-lens/criteria-sets/{set_id}/archive").status_code
        == 404
    )


def test_interview_lab_attempt_history_is_user_scoped(client, switch_user):
    _seed_jobs()
    assert client.get("/api/v1/me").status_code == 200
    jobs = client.get("/api/v1/jobs?limit=10")
    assert jobs.status_code == 200
    job_id = jobs.json()["items"][0]["id"]

    lab = client.get(f"/api/v1/growth/interview-lab/jobs/{job_id}")
    assert lab.status_code == 200, lab.text
    assert {item["category"] for item in lab.json()["questions"]} >= {
        "BEHAVIORAL",
        "TECHNICAL",
        "SYSTEM_DESIGN",
        "SQL",
        "CODING",
    }
    assert lab.json()["execution_policy"]["remote_arbitrary_code_execution"] is False

    attempt = client.post(
        "/api/v1/growth/interview-lab/attempts",
        json={
            "job_id": job_id,
            "category": "CODING",
            "question": "Explain a safe deterministic solution.",
            "answer_text": "I would separate validation, transformation, and failure handling.",
            "notes": "Review edge cases.",
            "self_review": {"truthful": True},
        },
    )
    assert attempt.status_code == 201, attempt.text

    owner_lab = client.get(f"/api/v1/growth/interview-lab/jobs/{job_id}").json()
    assert len(owner_lab["attempts"]) == 1

    switch_user("clerk_user_b", "b@example.com")
    other_lab = client.get(f"/api/v1/growth/interview-lab/jobs/{job_id}")
    assert other_lab.status_code == 200
    assert other_lab.json()["attempts"] == []


def test_resume_share_session_and_trends_are_owner_scoped(client, switch_user, database_url: str):
    seeded = _seed_resume_and_job(client, database_url)
    created = client.post(
        "/api/v1/resume-shares",
        json={
            "resume_version_id": seeded["resume_version_id"],
            "label": "Tracked resume",
            "always_current": False,
            "allow_download": True,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
    )
    assert created.status_code == 200, created.text
    share = created.json()
    token = share["public_token"]
    headers = {"user-agent": "Mozilla/5.0 ApplyAI regression"}
    sid = "gap-closure-session-a"

    for event in (
        {"session_id": sid, "event_type": "VIEW"},
        {"session_id": sid, "event_type": "DWELL", "value": 75000},
        {"session_id": sid, "event_type": "SCROLL", "value": 80},
        {"session_id": sid, "event_type": "COPY", "metadata": {"target": "email"}},
    ):
        response = client.post(
            f"/api/v1/resume-shares/public/{token}/events",
            json=event,
            headers=headers,
        )
        assert response.status_code == 204, response.text

    sessions = client.get(f"/api/v1/resume-shares/{share['id']}/sessions")
    assert sessions.status_code == 200, sessions.text
    report = sessions.json()["sessions"][0]
    assert report["max_dwell_ms"] == 75000
    assert report["max_scroll_depth"] == 80
    assert report["measurement"]["viewer_identity_known"] is False
    assert report["measurement"]["company_identity_inferred"] is False
    assert report["measurement"]["raw_ip_stored"] is False

    trends = client.get(f"/api/v1/resume-shares/{share['id']}/trends?days=30")
    assert trends.status_code == 200
    assert trends.json()["current"]["views"] == 1
    assert trends.json()["current"]["deep_read_rate"] == 1.0

    switch_user("clerk_user_b", "b@example.com")
    assert client.get(f"/api/v1/resume-shares/{share['id']}/sessions").status_code == 404
    assert client.get(f"/api/v1/resume-shares/{share['id']}/trends?days=30").status_code == 404
