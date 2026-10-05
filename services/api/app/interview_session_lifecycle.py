"""Shared privacy/state guards for canonical ApplyAI mock interviews."""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.preparation_models import MockInterviewSession


def ensure_available(row: MockInterviewSession, *, writing: bool = False, capture: bool = False) -> None:
    expires = row.retention_expires_at
    if expires is not None:
        expires = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
        if expires <= datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Interview retention period has expired; delete this session or start another")
    if writing and row.status != "IN_PROGRESS":
        raise HTTPException(status_code=409, detail="Interview is not in progress")
    if capture and row.transcript_consent_at is None:
        raise HTTPException(status_code=409, detail="Explicit recording and transcript consent is required")
