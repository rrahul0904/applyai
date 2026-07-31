from __future__ import annotations

import uuid
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.job_source_models import JobSourceDiscovery
from app.jobs.discovery import request_key_for
from app.jobs.web_security import PublicUrlRejected, validate_public_http_url
from app.models import User


router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobUrlImportRequest(BaseModel):
    url: HttpUrl


class JobUrlImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    input_url: str
    detected_provider: str | None
    canonical_url: str | None
    apply_url: str | None
    job_id: uuid.UUID | None
    access_policy: str
    error_category: str | None
    created_at: datetime
    updated_at: datetime


def _response(record: JobSourceDiscovery) -> JobUrlImportResponse:
    return JobUrlImportResponse(
        id=record.id,
        status=record.status,
        input_url=record.input_url,
        detected_provider=record.detected_provider,
        canonical_url=record.canonical_url,
        apply_url=record.apply_url,
        job_id=record.job_id,
        access_policy=record.access_policy,
        error_category=record.error_category,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post(
    "/import-url",
    response_model=JobUrlImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def import_job_url(
    payload: JobUrlImportRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JobUrlImportResponse:
    try:
        canonical_input = validate_public_http_url(str(payload.url))
    except PublicUrlRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "UNSAFE_JOB_URL", "message": str(exc)},
        ) from exc

    request_key = request_key_for(user.id, canonical_input)
    existing = session.scalar(
        select(JobSourceDiscovery).where(JobSourceDiscovery.request_key == request_key)
    )
    if existing is not None:
        return _response(existing)

    record = JobSourceDiscovery(
        user_id=user.id,
        request_key=request_key,
        input_url=canonical_input,
        input_domain=(urlsplit(canonical_input).hostname or "").casefold(),
        discovered_url=canonical_input,
        status="QUEUED",
        access_policy="UNKNOWN",
        evidence=["candidate-submitted-url"],
    )
    session.add(record)
    session.flush()
    add_task_outbox_event(
        session,
        task=Task(
            task_type="JOB_URL_IMPORT",
            payload={"discovery_id": str(record.id)},
            idempotency_key=f"job-url-import:{record.id}",
        ),
        aggregate_type="JOB_SOURCE_DISCOVERY",
        aggregate_id=record.id,
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(JobSourceDiscovery).where(JobSourceDiscovery.request_key == request_key)
        )
        if existing is None:
            raise
        return _response(existing)
    session.refresh(record)
    return _response(record)


@router.get("/import-url/{discovery_id}", response_model=JobUrlImportResponse)
def get_job_url_import(
    discovery_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JobUrlImportResponse:
    record = session.scalar(
        select(JobSourceDiscovery).where(
            JobSourceDiscovery.id == discovery_id,
            JobSourceDiscovery.user_id == user.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Job URL import not found")
    return _response(record)
