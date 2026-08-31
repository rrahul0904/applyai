from __future__ import annotations

import csv
import hashlib
import io
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.storage import ObjectStorageProvider, get_object_storage
from app.models import (
    Application,
    CandidateProfile,
    Company,
    Job,
    Notification,
    Resume,
    ResumeVersion,
    User,
)
from app.resume_share_models import ResumeShareEvent, ResumeShareLink


router = APIRouter(prefix="/resume-shares", tags=["resume-shares"])

_ALLOWED_EVENTS = {"VIEW", "DWELL", "SCROLL", "DOWNLOAD", "LINK_CLICK", "COPY"}
_BOT_MARKERS = (
    "bot",
    "crawler",
    "spider",
    "slackbot",
    "linkedinbot",
    "facebookexternalhit",
    "skypeuripreview",
    "teams",
    "curl/",
    "wget/",
)


class ResumeShareCreate(BaseModel):
    resume_version_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    label: str | None = Field(default=None, max_length=200)
    channel: str | None = Field(default=None, max_length=80)
    always_current: bool = True
    allow_download: bool = True
    expires_at: datetime | None = None


class ResumeShareUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    channel: str | None = Field(default=None, max_length=80)
    allow_download: bool | None = None
    expires_at: datetime | None = None
    status: Literal["ACTIVE", "REVOKED"] | None = None


class PublicEventWrite(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)
    event_type: Literal["VIEW", "DWELL", "SCROLL", "LINK_CLICK", "COPY"]
    value: int | None = None
    target: str | None = Field(default=None, max_length=80)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _share_active(share: ResumeShareLink) -> bool:
    if share.status != "ACTIVE":
        return False
    if share.expires_at is None:
        return True
    expires_at = share.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > _now()


def _session_hash(share: ResumeShareLink, client_session_id: str) -> str:
    return hashlib.sha256(f"{share.id}:{client_session_id}".encode("utf-8")).hexdigest()


def _suspected_bot(request: Request) -> bool:
    user_agent = request.headers.get("user-agent", "").casefold()
    return any(marker in user_agent for marker in _BOT_MARKERS)


def _safe_event_value(event_type: str, value: int | None) -> int | None:
    if value is None:
        return None
    if event_type == "DWELL":
        return max(0, min(value, 3_600_000))
    if event_type == "SCROLL":
        return max(0, min(value, 100))
    return max(0, min(value, 10_000))


def _latest_version(session: Session, *, user_id: uuid.UUID, resume_id: uuid.UUID | None = None) -> ResumeVersion | None:
    statement = select(ResumeVersion).where(
        ResumeVersion.user_id == user_id,
        ResumeVersion.upload_status == "UPLOADED",
    )
    if resume_id is not None:
        statement = statement.where(ResumeVersion.resume_id == resume_id)
    return session.scalar(
        statement.order_by(ResumeVersion.created_at.desc(), ResumeVersion.version_number.desc()).limit(1)
    )


def _resolved_version(session: Session, share: ResumeShareLink) -> ResumeVersion | None:
    if not share.always_current and share.pinned_resume_version_id is not None:
        version = session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == share.pinned_resume_version_id,
                ResumeVersion.user_id == share.user_id,
                ResumeVersion.upload_status == "UPLOADED",
            )
        )
        if version is not None:
            return version
    return _latest_version(session, user_id=share.user_id, resume_id=share.resume_id)


def _owned_share(session: Session, *, share_id: uuid.UUID, user: User) -> ResumeShareLink:
    share = session.scalar(
        select(ResumeShareLink).where(
            ResumeShareLink.id == share_id,
            ResumeShareLink.user_id == user.id,
        )
    )
    if share is None:
        raise HTTPException(status_code=404, detail="Resume share link not found")
    return share


def _public_share(session: Session, token: str) -> ResumeShareLink:
    share = session.scalar(select(ResumeShareLink).where(ResumeShareLink.public_token == token))
    if share is None:
        raise HTTPException(status_code=404, detail="Resume share link not found")
    if not _share_active(share):
        raise HTTPException(status_code=410, detail="This resume share link is no longer active")
    return share


def _job_context(session: Session, share: ResumeShareLink) -> dict[str, str | None]:
    if share.job_id is None:
        return {"job_id": None, "job_title": None, "company_name": None}
    row = session.execute(
        select(Job, Company)
        .join(Company, Company.id == Job.company_id)
        .where(Job.id == share.job_id)
    ).first()
    if row is None:
        return {"job_id": str(share.job_id), "job_title": None, "company_name": None}
    job, company = row
    return {
        "job_id": str(job.id),
        "job_title": job.title,
        "company_name": company.canonical_name,
    }


def _score_session(events: list[ResumeShareEvent]) -> tuple[int, str, dict[str, int]]:
    views = sum(1 for event in events if event.event_type == "VIEW")
    downloads = sum(1 for event in events if event.event_type == "DOWNLOAD")
    clicks = sum(1 for event in events if event.event_type == "LINK_CLICK")
    copies = sum(1 for event in events if event.event_type == "COPY")
    dwell_ms = max((event.event_value or 0 for event in events if event.event_type == "DWELL"), default=0)
    scroll = max((event.event_value or 0 for event in events if event.event_type == "SCROLL"), default=0)

    score = 0.0
    if views:
        score += 20
    score += min(30, (dwell_ms / 180_000) * 30)
    score += min(25, (scroll / 100) * 25)
    if downloads:
        score += 10
    score += min(10, clicks * 5)
    score += min(5, copies * 5)
    if views > 1:
        score += 10
    final_score = min(100, round(score))
    intent = "DEEP_READ" if final_score >= 75 else "ENGAGED" if final_score >= 45 else "BROWSED"
    return final_score, intent, {
        "views": views,
        "dwell_ms": dwell_ms,
        "scroll_depth": scroll,
        "downloads": downloads,
        "link_clicks": clicks,
        "copies": copies,
    }


def _analytics(session: Session, share: ResumeShareLink) -> dict[str, Any]:
    events = list(
        session.scalars(
            select(ResumeShareEvent)
            .where(ResumeShareEvent.share_id == share.id)
            .order_by(ResumeShareEvent.occurred_at.asc())
        ).all()
    )
    bot_events = sum(1 for event in events if event.suspected_bot)
    human_events = [event for event in events if not event.suspected_bot]
    grouped: dict[str, list[ResumeShareEvent]] = defaultdict(list)
    for event in human_events:
        grouped[event.session_hash].append(event)

    sessions: list[dict[str, Any]] = []
    for session_hash, session_events in grouped.items():
        score, intent, counters = _score_session(session_events)
        sessions.append(
            {
                "viewer": f"Viewer {session_hash[:8]}",
                "session_key": session_hash[:12],
                "first_seen_at": session_events[0].occurred_at.isoformat(),
                "last_seen_at": session_events[-1].occurred_at.isoformat(),
                "interest_score": score,
                "intent": intent,
                **counters,
            }
        )
    sessions.sort(key=lambda item: item["last_seen_at"], reverse=True)
    view_events = [event for event in human_events if event.event_type == "VIEW"]
    returning_viewers = sum(1 for events_for_session in grouped.values() if sum(1 for e in events_for_session if e.event_type == "VIEW") > 1)
    scores = [item["interest_score"] for item in sessions]

    timeline = [
        {
            "viewer": f"Viewer {event.session_hash[:8]}",
            "event_type": event.event_type,
            "value": event.event_value,
            "target": event.metadata_json.get("target") if isinstance(event.metadata_json, dict) else None,
            "occurred_at": event.occurred_at.isoformat(),
        }
        for event in reversed(human_events[-100:])
    ]
    return {
        "views": len(view_events),
        "unique_viewers": len({event.session_hash for event in view_events}),
        "returning_viewers": returning_viewers,
        "downloads": sum(1 for event in human_events if event.event_type == "DOWNLOAD"),
        "link_clicks": sum(1 for event in human_events if event.event_type == "LINK_CLICK"),
        "copies": sum(1 for event in human_events if event.event_type == "COPY"),
        "average_interest_score": round(sum(scores) / len(scores)) if scores else 0,
        "suspected_bot_events": bot_events,
        "sessions": sessions,
        "timeline": timeline,
    }


def _owner_payload(session: Session, share: ResumeShareLink) -> dict[str, Any]:
    version = _resolved_version(session, share)
    return {
        "id": str(share.id),
        "public_token": share.public_token,
        "public_path": f"/r/{share.public_token}",
        "label": share.label,
        "channel": share.channel,
        "status": share.status,
        "active": _share_active(share),
        "always_current": share.always_current,
        "allow_download": share.allow_download,
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
        "application_id": str(share.application_id) if share.application_id else None,
        "resume_version_id": str(version.id) if version else None,
        "filename": version.filename if version else None,
        "created_at": share.created_at.isoformat(),
        "updated_at": share.updated_at.isoformat(),
        **_job_context(session, share),
        "analytics": _analytics(session, share),
        "privacy": {
            "raw_ip_stored": False,
            "cross_link_fingerprinting": False,
            "company_identity_inferred": False,
            "engagement_is_hiring_probability": False,
        },
    }


def _record_event(
    session: Session,
    *,
    share: ResumeShareLink,
    client_session_id: str,
    event_type: str,
    request: Request,
    value: int | None = None,
    target: str | None = None,
) -> None:
    if event_type not in _ALLOWED_EVENTS:
        raise HTTPException(status_code=422, detail="Unsupported resume share event")
    session_hash = _session_hash(share, client_session_id)
    bot = _suspected_bot(request)
    prior_same_type = session.scalar(
        select(ResumeShareEvent)
        .where(
            ResumeShareEvent.share_id == share.id,
            ResumeShareEvent.session_hash == session_hash,
            ResumeShareEvent.event_type == event_type,
            ResumeShareEvent.suspected_bot.is_(False),
        )
        .order_by(ResumeShareEvent.occurred_at.desc())
        .limit(1)
    )
    event = ResumeShareEvent(
        share_id=share.id,
        session_hash=session_hash,
        event_type=event_type,
        event_value=_safe_event_value(event_type, value),
        metadata_json={"target": target} if target else {},
        suspected_bot=bot,
    )
    session.add(event)

    if not bot and event_type == "VIEW":
        notification_type = "RESUME_SHARE_VIEWED" if prior_same_type is None else "RESUME_SHARE_RETURNED"
        if prior_same_type is None or notification_type == "RESUME_SHARE_RETURNED":
            session.add(
                Notification(
                    user_id=share.user_id,
                    notification_type=notification_type,
                    payload={
                        "share_id": str(share.id),
                        "label": share.label,
                        "job_id": str(share.job_id) if share.job_id else None,
                        "application_id": str(share.application_id) if share.application_id else None,
                    },
                )
            )
    elif not bot and event_type == "DOWNLOAD" and prior_same_type is None:
        session.add(
            Notification(
                user_id=share.user_id,
                notification_type="RESUME_SHARE_DOWNLOADED",
                payload={
                    "share_id": str(share.id),
                    "label": share.label,
                    "job_id": str(share.job_id) if share.job_id else None,
                    "application_id": str(share.application_id) if share.application_id else None,
                },
            )
        )
    session.commit()


@router.post("")
def create_resume_share(
    payload: ResumeShareCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    version = None
    if payload.resume_version_id is not None:
        version = session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == payload.resume_version_id,
                ResumeVersion.user_id == user.id,
                ResumeVersion.upload_status == "UPLOADED",
            )
        )
        if version is None:
            raise HTTPException(status_code=404, detail="Resume version not found")
    else:
        version = _latest_version(session, user_id=user.id)
    if version is None:
        raise HTTPException(status_code=409, detail="Upload a resume before creating a share link")

    resume = session.scalar(select(Resume).where(Resume.id == version.resume_id, Resume.user_id == user.id))
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    application = None
    job_id = payload.job_id
    if payload.application_id is not None:
        application = session.scalar(
            select(Application).where(
                Application.id == payload.application_id,
                Application.user_id == user.id,
            )
        )
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if job_id is not None and application.job_id != job_id:
            raise HTTPException(status_code=422, detail="Application does not belong to the selected job")
        job_id = application.job_id
    if job_id is not None and session.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    expires_at = payload.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= _now():
            raise HTTPException(status_code=422, detail="Expiry must be in the future")

    label = (payload.label or "Resume share").strip() or "Resume share"
    share = ResumeShareLink(
        user_id=user.id,
        resume_id=resume.id,
        pinned_resume_version_id=None if payload.always_current else version.id,
        job_id=job_id,
        application_id=application.id if application else None,
        public_token=secrets.token_urlsafe(24),
        label=label[:200],
        channel=payload.channel.strip()[:80] if payload.channel else None,
        always_current=payload.always_current,
        allow_download=payload.allow_download,
        status="ACTIVE",
        expires_at=expires_at,
    )
    session.add(share)
    session.commit()
    session.refresh(share)
    return _owner_payload(session, share)


@router.get("")
def list_resume_shares(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    shares = session.scalars(
        select(ResumeShareLink)
        .where(ResumeShareLink.user_id == user.id)
        .order_by(ResumeShareLink.created_at.desc())
    ).all()
    return [_owner_payload(session, share) for share in shares]


@router.get("/{share_id}")
def get_resume_share(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return _owner_payload(session, _owned_share(session, share_id=share_id, user=user))


@router.patch("/{share_id}")
def update_resume_share(
    share_id: uuid.UUID,
    payload: ResumeShareUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    share = _owned_share(session, share_id=share_id, user=user)
    if payload.label is not None:
        share.label = payload.label.strip()
    if "channel" in payload.model_fields_set:
        share.channel = payload.channel.strip() if payload.channel else None
    if payload.allow_download is not None:
        share.allow_download = payload.allow_download
    if "expires_at" in payload.model_fields_set:
        expires_at = payload.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= _now():
                raise HTTPException(status_code=422, detail="Expiry must be in the future")
        share.expires_at = expires_at
    if payload.status is not None:
        share.status = payload.status
    session.commit()
    session.refresh(share)
    return _owner_payload(session, share)


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume_share(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    share = _owned_share(session, share_id=share_id, user=user)
    session.execute(delete(ResumeShareLink).where(ResumeShareLink.id == share.id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{share_id}/export.csv")
def export_resume_share_csv(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    share = _owned_share(session, share_id=share_id, user=user)
    analytics = _analytics(session, share)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["viewer", "intent", "interest_score", "views", "dwell_ms", "scroll_depth", "downloads", "link_clicks", "copies", "first_seen_at", "last_seen_at"])
    for item in analytics["sessions"]:
        writer.writerow([
            item["viewer"], item["intent"], item["interest_score"], item["views"], item["dwell_ms"],
            item["scroll_depth"], item["downloads"], item["link_clicks"], item["copies"],
            item["first_seen_at"], item["last_seen_at"],
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="resume-share-{share.id}.csv"'},
    )


@router.get("/public/{token}")
def public_resume_share(
    token: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    share = _public_share(session, token)
    version = _resolved_version(session, share)
    if version is None:
        raise HTTPException(status_code=410, detail="The shared resume is unavailable")
    owner = session.get(User, share.user_id)
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == share.user_id))
    display_name = "Candidate"
    if owner is not None:
        name = " ".join(part for part in (owner.first_name, owner.last_name) if part).strip()
        display_name = name or "Candidate"
    return {
        "label": share.label,
        "candidate_display_name": display_name,
        "headline": profile.headline if profile else None,
        "filename": version.filename,
        "content_type": version.content_type,
        "allow_download": share.allow_download,
        "file_path": f"/api/public-backend/resume-shares/public/{share.public_token}/file",
        "download_path": f"/api/public-backend/resume-shares/public/{share.public_token}/download",
        "privacy_notice": "This link records privacy-preserving engagement events for the resume owner. ApplyAI does not store raw IP addresses or use cross-link viewer fingerprinting for Resume Share Intelligence.",
    }


@router.post("/public/{token}/events", status_code=status.HTTP_204_NO_CONTENT)
def record_public_resume_event(
    token: str,
    payload: PublicEventWrite,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    share = _public_share(session, token)
    _record_event(
        session,
        share=share,
        client_session_id=payload.session_id,
        event_type=payload.event_type,
        request=request,
        value=payload.value,
        target=payload.target,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/public/{token}/file")
def public_resume_file(
    token: str,
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
) -> Response:
    share = _public_share(session, token)
    version = _resolved_version(session, share)
    if version is None:
        raise HTTPException(status_code=410, detail="The shared resume is unavailable")
    filename = Path(version.filename).name.replace('"', "")
    return Response(
        content=storage.get(key=version.storage_key),
        media_type=version.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/public/{token}/download")
def download_public_resume(
    token: str,
    request: Request,
    sid: str | None = Query(default=None, min_length=8, max_length=128),
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
) -> Response:
    share = _public_share(session, token)
    if not share.allow_download:
        raise HTTPException(status_code=403, detail="Downloads are disabled for this resume link")
    version = _resolved_version(session, share)
    if version is None:
        raise HTTPException(status_code=410, detail="The shared resume is unavailable")
    if sid:
        _record_event(
            session,
            share=share,
            client_session_id=sid,
            event_type="DOWNLOAD",
            request=request,
        )
    filename = Path(version.filename).name.replace('"', "")
    return Response(
        content=storage.get(key=version.storage_key),
        media_type=version.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )
