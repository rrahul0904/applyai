from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.job_source_models import JobSourceDiscovery


router = APIRouter(
    prefix="/internal/job-source-discoveries",
    tags=["internal-job-source-discoveries"],
    dependencies=[Depends(require_internal_api)],
)


class DiscoveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    company_id: uuid.UUID | None
    source_registry_id: uuid.UUID | None
    job_id: uuid.UUID | None
    input_url: str
    input_domain: str
    discovered_careers_url: str | None
    discovered_url: str | None
    resolved_url: str | None
    canonical_url: str | None
    apply_url: str | None
    detected_provider: str | None
    confidence: Decimal | None
    status: str
    access_policy: str
    evidence: list
    etag: str | None
    last_modified: str | None
    content_hash: str | None
    attempt_count: int
    error_category: str | None
    error_summary: str | None
    discovered_at: datetime
    verified_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _get(session: Session, discovery_id: uuid.UUID) -> JobSourceDiscovery:
    record = session.get(JobSourceDiscovery, discovery_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job source discovery not found")
    return record


@router.get("", response_model=list[DiscoveryResponse])
def list_discoveries(
    status: str | None = Query(default=None, max_length=32),
    provider: str | None = Query(default=None, max_length=48),
    access_policy: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    query = select(JobSourceDiscovery).order_by(
        JobSourceDiscovery.created_at.desc(),
        JobSourceDiscovery.id.desc(),
    )
    if status:
        query = query.where(JobSourceDiscovery.status == status.upper())
    if provider:
        query = query.where(JobSourceDiscovery.detected_provider == provider.upper())
    if access_policy:
        query = query.where(JobSourceDiscovery.access_policy == access_policy.upper())
    return list(session.scalars(query.limit(limit)))


@router.get("/{discovery_id}", response_model=DiscoveryResponse)
def get_discovery(
    discovery_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    return _get(session, discovery_id)


@router.post("/{discovery_id}/retry", response_model=DiscoveryResponse)
def retry_discovery(
    discovery_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    record = _get(session, discovery_id)
    if record.status == "VERIFIED":
        return record
    record.status = "QUEUED"
    record.error_category = None
    record.error_summary = None
    record.completed_at = None
    add_task_outbox_event(
        session,
        task=Task(
            task_type="JOB_URL_IMPORT" if record.user_id else "SOURCE_DISCOVERY",
            payload={"discovery_id": str(record.id)},
            idempotency_key=f"discovery-retry:{record.id}:{record.attempt_count + 1}",
        ),
        aggregate_type="JOB_SOURCE_DISCOVERY",
        aggregate_id=record.id,
    )
    session.commit()
    session.refresh(record)
    return record
