from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Application, Notification, Resume, ResumeVersion, User
from tests.helpers import create_job


def _seed_resume_and_job(client, database_url: str):
    assert client.get("/api/v1/me").status_code == 200
    engine = create_engine(database_url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.clerk_user_id == "clerk_user_a"))
        assert user is not None
        job = create_job(session)
        resume = Resume(user_id=user.id, name="master", is_master=True)
        session.add(resume)
        session.flush()
        version = ResumeVersion(
            resume_id=resume.id,
            user_id=user.id,
            version_number=1,
            filename="candidate.pdf",
            content_type="application/pdf",
            storage_key=f"resumes/{user.id}/candidate.pdf",
            file_size=24,
            upload_status="UPLOADED",
            processing_status="COMPLETED",
        )
        session.add(version)
        session.flush()
        application = Application(user_id=user.id, job_id=job.id, current_status="PREPARING")
        session.add(application)
        session.commit()
        values = {
            "user_id": str(user.id),
            "job_id": str(job.id),
            "resume_version_id": str(version.id),
            "application_id": str(application.id),
            "storage_key": version.storage_key,
        }
    engine.dispose()
    client.storage.objects[values["storage_key"]] = b"%PDF-1.4\nApplyAI resume\n%%EOF"  # type: ignore[attr-defined]
    client.storage.content_types[values["storage_key"]] = "application/pdf"  # type: ignore[attr-defined]
    return values


def test_resume_share_tracks_privacy_preserving_engagement(client, database_url: str):
    seeded = _seed_resume_and_job(client, database_url)
    response = client.post(
        "/api/v1/resume-shares",
        json={
            "resume_version_id": seeded["resume_version_id"],
            "job_id": seeded["job_id"],
            "application_id": seeded["application_id"],
            "label": "Northstar application",
            "channel": "application",
            "always_current": False,
            "allow_download": True,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    share = response.json()
    assert share["label"] == "Northstar application"
    assert share["company_name"] == "Northstar Health"
    assert share["job_title"] == "Product Operations Manager"
    assert share["privacy"] == {
        "raw_ip_stored": False,
        "cross_link_fingerprinting": False,
        "company_identity_inferred": False,
        "engagement_is_hiring_probability": False,
    }

    token = share["public_token"]
    public = client.get(f"/api/v1/resume-shares/public/{token}")
    assert public.status_code == 200
    assert public.json()["candidate_display_name"] == "A"
    assert "does not store raw IP" in public.json()["privacy_notice"]

    headers = {"user-agent": "Mozilla/5.0 ApplyAI test browser"}
    sid = "viewer-session-12345"
    for payload in (
        {"session_id": sid, "event_type": "VIEW"},
        {"session_id": sid, "event_type": "DWELL", "value": 150000},
        {"session_id": sid, "event_type": "SCROLL", "value": 92},
        {"session_id": sid, "event_type": "VIEW"},
    ):
        event = client.post(
            f"/api/v1/resume-shares/public/{token}/events",
            json=payload,
            headers=headers,
        )
        assert event.status_code == 204, event.text

    download = client.get(
        f"/api/v1/resume-shares/public/{token}/download?sid={sid}",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")
    assert "attachment" in download.headers["content-disposition"]

    bot = client.post(
        f"/api/v1/resume-shares/public/{token}/events",
        json={"session_id": "preview-bot-session", "event_type": "VIEW"},
        headers={"user-agent": "Slackbot-LinkExpanding 1.0"},
    )
    assert bot.status_code == 204

    detail = client.get(f"/api/v1/resume-shares/{share['id']}")
    assert detail.status_code == 200
    analytics = detail.json()["analytics"]
    assert analytics["views"] == 2
    assert analytics["unique_viewers"] == 1
    assert analytics["returning_viewers"] == 1
    assert analytics["downloads"] == 1
    assert analytics["suspected_bot_events"] == 1
    assert analytics["sessions"][0]["intent"] == "DEEP_READ"
    assert analytics["sessions"][0]["interest_score"] >= 75

    export = client.get(f"/api/v1/resume-shares/{share['id']}/export.csv")
    assert export.status_code == 200
    assert "DEEP_READ" in export.text
    assert "viewer,intent,interest_score" in export.text

    engine = create_engine(database_url)
    with Session(engine) as session:
        notifications = list(
            session.scalars(
                select(Notification).where(Notification.user_id == uuid.UUID(seeded["user_id"]))
            ).all()
        )
        kinds = [item.notification_type for item in notifications]
        assert "RESUME_SHARE_VIEWED" in kinds
        assert "RESUME_SHARE_RETURNED" in kinds
        assert "RESUME_SHARE_DOWNLOADED" in kinds
    engine.dispose()


def test_resume_share_can_be_revoked_and_is_owner_scoped(client, switch_user, database_url: str):
    seeded = _seed_resume_and_job(client, database_url)
    created = client.post(
        "/api/v1/resume-shares",
        json={
            "resume_version_id": seeded["resume_version_id"],
            "label": "Referral link",
            "always_current": True,
        },
    )
    assert created.status_code == 200
    share = created.json()

    revoked = client.patch(
        f"/api/v1/resume-shares/{share['id']}",
        json={"status": "REVOKED", "allow_download": False},
    )
    assert revoked.status_code == 200
    assert revoked.json()["active"] is False
    assert client.get(f"/api/v1/resume-shares/public/{share['public_token']}").status_code == 410

    switch_user("clerk_user_b", "b@example.com")
    assert client.get("/api/v1/resume-shares").json() == []
    assert client.get(f"/api/v1/resume-shares/{share['id']}").status_code == 404
