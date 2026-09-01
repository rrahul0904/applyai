from app.jobs.seed import seed_development_jobs
from tests.test_recruiter_lens import candidate_profile


def _seed_jobs() -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        seed_development_jobs(session)


def test_recruiter_lens_report_share_is_candidate_controlled_and_revocable(client, switch_user):
    _seed_jobs()
    assert client.put("/api/v1/profile", json=candidate_profile()).status_code == 200
    selected = client.get("/api/v1/career-v1/matches?limit=10").json()["items"][0]
    job_id = selected["job_id"]

    created = client.post(
        f"/api/v1/recruiter-lens/jobs/{job_id}/report-shares?mode=TECHNICAL"
    )
    assert created.status_code == 201, created.text
    share = created.json()
    assert share["privacy"] == {
        "candidate_controlled": True,
        "named_viewer_tracking": False,
        "employer_decision": False,
    }
    assert share["public_path"].startswith("/recruiter-report/")
    token = share["public_path"].split("/")[-1]

    public = client.get(f"/api/v1/recruiter-lens/public/reports/{token}")
    assert public.status_code == 200, public.text
    payload = public.json()
    assert payload["mode"] == "TECHNICAL"
    assert payload["report"]["candidate_controlled"] is True
    assert payload["report"]["employer_decision"] is False
    assert payload["privacy"] == {
        "named_viewer_tracking": False,
        "company_identity_inferred": False,
        "hiring_probability": False,
    }
    assert "not an employer score" in payload["disclaimer"].lower()

    switch_user("clerk_user_b", "b@example.com")
    assert client.get("/api/v1/recruiter-lens/report-shares").json() == []
    assert (
        client.post(f"/api/v1/recruiter-lens/report-shares/{share['id']}/revoke").status_code
        == 404
    )

    switch_user("clerk_user_a", "a@example.com")
    revoked = client.post(f"/api/v1/recruiter-lens/report-shares/{share['id']}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True
    assert client.get(f"/api/v1/recruiter-lens/public/reports/{token}").status_code == 404
