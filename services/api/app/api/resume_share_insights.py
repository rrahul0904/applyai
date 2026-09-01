from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import User
from app.resume_share_models import ResumeShareEvent, ResumeShareLink

router = APIRouter(prefix="/resume-shares", tags=["resume-share insights"])


def _owned_share(session: Session, share_id: uuid.UUID, user: User) -> ResumeShareLink:
    share = session.scalar(
        select(ResumeShareLink).where(
            ResumeShareLink.id == share_id,
            ResumeShareLink.user_id == user.id,
        )
    )
    if share is None:
        raise HTTPException(status_code=404, detail="Resume share link not found")
    return share


def _human_events(session: Session, share_id: uuid.UUID) -> list[ResumeShareEvent]:
    return list(
        session.scalars(
            select(ResumeShareEvent)
            .where(
                ResumeShareEvent.share_id == share_id,
                ResumeShareEvent.suspected_bot.is_(False),
            )
            .order_by(ResumeShareEvent.occurred_at.asc())
        ).all()
    )


def _session_report(events: list[ResumeShareEvent]) -> dict[str, Any]:
    views = [event for event in events if event.event_type == "VIEW"]
    dwell = max((event.event_value or 0 for event in events if event.event_type == "DWELL"), default=0)
    scroll = max((event.event_value or 0 for event in events if event.event_type == "SCROLL"), default=0)
    return {
        "first_seen_at": events[0].occurred_at.isoformat(),
        "last_seen_at": events[-1].occurred_at.isoformat(),
        "view_count": len(views),
        "return_visit": len(views) > 1,
        "max_dwell_ms": dwell,
        "max_scroll_depth": scroll,
        "downloads": sum(event.event_type == "DOWNLOAD" for event in events),
        "link_clicks": sum(event.event_type == "LINK_CLICK" for event in events),
        "copies": sum(event.event_type == "COPY" for event in events),
        "sequence": [
            {
                "event_type": event.event_type,
                "value": event.event_value,
                "target": event.metadata_json.get("target") if isinstance(event.metadata_json, dict) else None,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in events[-100:]
        ],
        "measurement": {
            "viewer_identity_known": False,
            "company_identity_inferred": False,
            "raw_ip_stored": False,
            "pdf_page_heatmap_available": False,
        },
    }


@router.get("/{share_id}/sessions")
def resume_share_sessions(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    _owned_share(session, share_id, user)
    grouped: dict[str, list[ResumeShareEvent]] = defaultdict(list)
    for event in _human_events(session, share_id):
        grouped[event.session_hash].append(event)
    sessions = []
    for session_hash, events in grouped.items():
        sessions.append({"session_key": session_hash[:12], **_session_report(events)})
    sessions.sort(key=lambda row: row["last_seen_at"], reverse=True)
    return {
        "share_id": str(share_id),
        "sessions": sessions,
        "privacy_note": "Sessions are anonymous per-link pseudonyms. ApplyAI does not infer named viewers or company identity.",
    }


def _window_metrics(events: list[ResumeShareEvent], start: datetime, end: datetime) -> dict[str, Any]:
    window = [event for event in events if start <= event.occurred_at < end]
    sessions: dict[str, list[ResumeShareEvent]] = defaultdict(list)
    for event in window:
        sessions[event.session_hash].append(event)
    views = [event for event in window if event.event_type == "VIEW"]
    return_sessions = sum(
        1 for grouped in sessions.values()
        if sum(event.event_type == "VIEW" for event in grouped) > 1
    )
    dwell_values = [
        max((event.event_value or 0 for event in grouped if event.event_type == "DWELL"), default=0)
        for grouped in sessions.values()
    ]
    deep_reads = 0
    for grouped in sessions.values():
        dwell = max((event.event_value or 0 for event in grouped if event.event_type == "DWELL"), default=0)
        scroll = max((event.event_value or 0 for event in grouped if event.event_type == "SCROLL"), default=0)
        if dwell >= 60_000 and scroll >= 60:
            deep_reads += 1
    return {
        "views": len(views),
        "unique_sessions": len({event.session_hash for event in views}),
        "return_sessions": return_sessions,
        "average_dwell_ms": round(sum(dwell_values) / len(dwell_values)) if dwell_values else 0,
        "deep_read_rate": round(deep_reads / len(sessions), 3) if sessions else 0,
        "downloads": sum(event.event_type == "DOWNLOAD" for event in window),
    }


@router.get("/{share_id}/trends")
def resume_share_trends(
    share_id: uuid.UUID,
    days: int = Query(default=30, ge=7, le=90),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if days not in {7, 30, 90}:
        raise HTTPException(status_code=422, detail="Trend window must be 7, 30, or 90 days")
    _owned_share(session, share_id, user)
    events = _human_events(session, share_id)
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    current = _window_metrics(events, current_start, now)
    previous = _window_metrics(events, previous_start, current_start)
    return {
        "share_id": str(share_id),
        "window_days": days,
        "current": current,
        "previous": previous,
        "comparison": {
            "views_delta": current["views"] - previous["views"],
            "unique_sessions_delta": current["unique_sessions"] - previous["unique_sessions"],
            "downloads_delta": current["downloads"] - previous["downloads"],
        },
        "sample_warning": "Interpret small samples cautiously." if current["unique_sessions"] < 5 else None,
    }
