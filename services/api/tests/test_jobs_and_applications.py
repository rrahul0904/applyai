from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.helpers import create_job


def seed_job(database_url):
    engine = create_engine(database_url)
    with Session(engine) as session:
        job = create_job(session)
        job_id = job.id
    engine.dispose()
    return job_id


def test_job_list_detail_and_saved_flow(client, database_url):
    job_id = seed_job(database_url)

    listing = client.get("/api/v1/jobs", params={"keyword": "operations", "work_mode": "hybrid"})
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1
    assert listing.json()["items"][0]["compensation_provenance"] == "EMPLOYER_DISCLOSED"
    assert listing.json()["items"][0]["saved"] is False

    detail = client.get(f"/api/v1/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["skills"] == ["Operations"]
    assert detail.json()["source_url"] == "https://example.test/jobs/001"

    assert client.post(f"/api/v1/jobs/{job_id}/save").status_code == 204
    saved = client.get("/api/v1/jobs/saved")
    assert saved.status_code == 200
    assert saved.json()["returned"] == 1
    assert saved.json()["next_cursor"] is None
    assert [item["id"] for item in saved.json()["items"]] == [str(job_id)]
    assert client.delete(f"/api/v1/jobs/{job_id}/save").status_code == 204
    empty_saved = client.get("/api/v1/jobs/saved").json()
    assert empty_saved["items"] == []
    assert empty_saved["returned"] == 0
    assert empty_saved["next_cursor"] is None


def test_saved_job_list_rejects_invalid_cursor_and_unbounded_limit(client):
    invalid_cursor = client.get("/api/v1/jobs/saved", params={"cursor": "not-a-valid-cursor"})
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["error"]["code"] == "INVALID_CURSOR"
    assert client.get("/api/v1/jobs/saved", params={"limit": 51}).status_code == 422
    assert client.get("/api/v1/jobs/saved", params={"limit": 0}).status_code == 422


def test_application_event_history_and_owner_isolation(
    client, database_url, switch_user
):
    job_id = seed_job(database_url)
    created = client.post("/api/v1/applications", json={"job_id": str(job_id)})
    assert created.status_code == 201
    application_id = created.json()["id"]
    assert created.json()["events"][0]["to_status"] == "PREPARING"

    updated = client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "APPLIED"},
    )
    assert updated.status_code == 200
    assert [event["to_status"] for event in updated.json()["events"]] == [
        "PREPARING",
        "APPLIED",
    ]

    listing = client.get("/api/v1/applications")
    assert listing.status_code == 200
    assert listing.json()["returned"] == 1
    assert listing.json()["next_cursor"] is None
    summary = listing.json()["items"][0]
    assert summary["id"] == application_id
    assert summary["job_id"] == str(job_id)
    assert summary["current_status"] == "APPLIED"
    assert summary["job"] == {
        "id": str(job_id),
        "title": "Product Operations Manager",
        "company_name": "Northstar Health",
        "location": "Boston, MA",
    }
    assert "events" not in summary
    assert "notes" not in summary

    switch_user("clerk_user_b", "b@example.com")
    isolated_listing = client.get("/api/v1/applications").json()
    assert isolated_listing["items"] == []
    assert isolated_listing["returned"] == 0
    isolated_get = client.get(f"/api/v1/applications/{application_id}")
    isolated_patch = client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "INTERVIEW"},
    )
    assert isolated_get.status_code == 404
    assert isolated_patch.status_code == 404


def test_application_list_rejects_invalid_cursor(client):
    response = client.get("/api/v1/applications", params={"cursor": "not-a-valid-cursor"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_application_list_limit_is_bounded(client):
    assert client.get("/api/v1/applications", params={"limit": 51}).status_code == 422
    assert client.get("/api/v1/applications", params={"limit": 0}).status_code == 422



def test_application_board_tracks_deadlines_interviews_and_offer_details(client, database_url):
    job_id = seed_job(database_url)
    created = client.post("/api/v1/applications", json={"job_id": str(job_id)})
    assert created.status_code == 201
    application_id = created.json()["id"]

    tracked = client.patch(
        f"/api/v1/applications/{application_id}/tracker",
        json={
            "deadline_at": "2030-06-01T17:00:00+00:00",
            "interview_at": "2030-05-20T14:00:00+00:00",
            "next_action_at": "2030-05-10T13:00:00+00:00",
            "source_channel": "Referral",
            "priority": "HIGH",
        },
    )
    assert tracked.status_code == 200, tracked.text
    assert tracked.json()["priority"] == "HIGH"
    assert tracked.json()["source_channel"] == "Referral"

    detail = client.get(f"/api/v1/applications/{application_id}")
    assert detail.status_code == 200
    assert detail.json()["tracker"]["interview_at"].startswith("2030-05-20")
    assert [event["to_status"] for event in detail.json()["events"]] == ["PREPARING"]

    board = client.get("/api/v1/applications/board")
    assert board.status_code == 200, board.text
    payload = board.json()
    assert payload["total"] == 1
    assert payload["counts"]["PREPARING"] == 1
    assert payload["items"][0]["tracker"]["priority"] == "HIGH"
    assert payload["items"][0]["overdue"] is False

    assert client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "OFFER"},
    ).status_code == 200
    offered = client.patch(
        f"/api/v1/applications/{application_id}/tracker",
        json={
            "offer_minimum": 150000,
            "offer_maximum": 175000,
            "offer_currency": "usd",
            "offer_notes": "Base salary range shared by recruiter.",
        },
    )
    assert offered.status_code == 200
    assert offered.json()["offer_currency"] == "USD"
    assert offered.json()["offer_minimum"] == 150000


def test_application_tracker_rejects_invalid_offer_range_and_priority(client, database_url):
    job_id = seed_job(database_url)
    application_id = client.post("/api/v1/applications", json={"job_id": str(job_id)}).json()["id"]

    invalid_range = client.patch(
        f"/api/v1/applications/{application_id}/tracker",
        json={"offer_minimum": 200000, "offer_maximum": 150000},
    )
    assert invalid_range.status_code == 422

    invalid_priority = client.patch(
        f"/api/v1/applications/{application_id}/tracker",
        json={"priority": "URGENT"},
    )
    assert invalid_priority.status_code == 422
