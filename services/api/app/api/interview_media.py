from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.storage import ObjectStorageProvider, get_object_storage
from app.models import User
from app.preparation_models import InterviewRecording, MockInterviewSession, UsageLedger

router = APIRouter(prefix="/career-v2", tags=["interview media"])
MAX_INTERVIEW_MEDIA_BYTES = 100 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {
    "audio/webm": "webm",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "video/webm": "webm",
    "video/mp4": "mp4",
}


class RecordingUploadIntentWrite(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    file_size: int = Field(gt=0, le=MAX_INTERVIEW_MEDIA_BYTES)
    media_type: str = Field(pattern="^(AUDIO|VIDEO)$")


class RecordingUploadCompleteWrite(BaseModel):
    storage_key: str = Field(min_length=1, max_length=2000)
    media_type: str = Field(pattern="^(AUDIO|VIDEO)$")
    transcript_text: str | None = Field(default=None, max_length=30000)
    duration_seconds: int | None = Field(default=None, ge=0, le=14400)
    provider: str = Field(default="browser", min_length=1, max_length=64)


def _owned_session(session: Session, user: User, session_id: uuid.UUID) -> MockInterviewSession:
    row = session.scalar(
        select(MockInterviewSession).where(
            MockInterviewSession.id == session_id,
            MockInterviewSession.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Mock interview not found")
    return row


def _safe_media_key(user_id: uuid.UUID, session_id: uuid.UUID, content_type: str) -> str:
    extension = ALLOWED_MEDIA_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported interview recording format",
        )
    return f"interviews/{user_id}/{session_id}/{uuid.uuid4()}.{extension}"


def _validate_key(user: User, interview: MockInterviewSession, key: str) -> None:
    expected = PurePosixPath("interviews") / str(user.id) / str(interview.id)
    candidate = PurePosixPath(key)
    if candidate.parent != expected or ".." in candidate.parts:
        raise HTTPException(status_code=403, detail="Recording storage key is not owned by this interview")


@router.post("/interviews/{session_id}/recording-upload-intents")
def create_recording_upload_intent(
    session_id: uuid.UUID,
    payload: RecordingUploadIntentWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
) -> dict:
    interview = _owned_session(session, user, session_id)
    key = _safe_media_key(user.id, interview.id, payload.content_type)
    if storage.supports_direct_upload:
        return {
            "upload_mode": "DIRECT",
            "storage_key": key,
            "upload_url": storage.create_presigned_put(
                key=key,
                content_type=payload.content_type,
                expires_in_seconds=900,
            ),
            "upload_headers": storage.direct_upload_headers(content_type=payload.content_type),
            "max_bytes": MAX_INTERVIEW_MEDIA_BYTES,
        }
    return {
        "upload_mode": "PROXY",
        "storage_key": key,
        "upload_url": f"/api/backend/api/v1/career-v2/interviews/{interview.id}/recordings/proxy?storage_key={key}",
        "upload_headers": {},
        "max_bytes": MAX_INTERVIEW_MEDIA_BYTES,
    }


@router.post("/interviews/{session_id}/recordings/proxy")
def proxy_recording_upload(
    session_id: uuid.UUID,
    storage_key: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
) -> dict:
    interview = _owned_session(session, user, session_id)
    _validate_key(user, interview, storage_key)
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported interview recording format")
    storage.put(key=storage_key, content=file.file, content_type=content_type)
    metadata = storage.head(key=storage_key)
    if metadata.size > MAX_INTERVIEW_MEDIA_BYTES:
        storage.delete(key=storage_key)
        raise HTTPException(status_code=413, detail="Interview recording exceeds the 100 MB limit")
    return {"storage_key": storage_key, "size": metadata.size, "content_type": content_type}


@router.post("/interviews/{session_id}/recording-upload-complete")
def complete_recording_upload(
    session_id: uuid.UUID,
    payload: RecordingUploadCompleteWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
) -> dict:
    interview = _owned_session(session, user, session_id)
    _validate_key(user, interview, payload.storage_key)
    try:
        metadata = storage.head(key=payload.storage_key)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail="Interview recording upload is not complete") from exc
    if metadata.size > MAX_INTERVIEW_MEDIA_BYTES:
        storage.delete(key=payload.storage_key)
        raise HTTPException(status_code=413, detail="Interview recording exceeds the 100 MB limit")
    existing = session.scalar(
        select(InterviewRecording).where(
            InterviewRecording.interview_session_id == interview.id,
            InterviewRecording.storage_key == payload.storage_key,
        )
    )
    if existing is None:
        existing = InterviewRecording(
            interview_session_id=interview.id,
            media_type=payload.media_type,
            storage_key=payload.storage_key,
            transcript_text=payload.transcript_text,
            duration_seconds=payload.duration_seconds,
            provider=payload.provider,
        )
        session.add(existing)
        session.flush()
        session.add(
            UsageLedger(
                user_id=user.id,
                feature="INTERVIEW_MEDIA_MINUTES",
                unit="minute",
                quantity=Decimal(str(round((payload.duration_seconds or 0) / 60, 4))),
                related_id=str(interview.id),
                metadata_json={"media_type": payload.media_type, "bytes": metadata.size},
            )
        )
    session.commit()
    return {
        "recording_id": existing.id,
        "storage_key": existing.storage_key,
        "media_type": existing.media_type,
        "duration_seconds": existing.duration_seconds,
        "transcript_available": bool(existing.transcript_text),
    }


@router.get("/interviews/{session_id}/recordings/{recording_id}")
def download_recording(
    session_id: uuid.UUID,
    recording_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
) -> Response:
    interview = _owned_session(session, user, session_id)
    recording = session.scalar(
        select(InterviewRecording).where(
            InterviewRecording.id == recording_id,
            InterviewRecording.interview_session_id == interview.id,
        )
    )
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    _validate_key(user, interview, recording.storage_key)
    metadata = storage.head(key=recording.storage_key)
    return Response(
        content=storage.get(key=recording.storage_key),
        media_type=metadata.content_type or ("video/webm" if recording.media_type == "VIDEO" else "audio/webm"),
        headers={"Cache-Control": "private, no-store"},
    )
