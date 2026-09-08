from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.operator_auth import require_operator_or_internal
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.durability_models import JobIngestionRun, TaskOutbox
from app.job_source_models import JobSourceRegistry
from app.models import Job
from app.postgres_queue_models import PostgresTask
from app.core.supabase_instance import supabase_instance_fingerprint
from app.operations_models import OperationsCertification


router = APIRouter(
    prefix="/internal/operations",
    tags=["internal-operations"],
    dependencies=[Depends(require_operator_or_internal)],
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _count(session: Session, model, *conditions) -> int:
    query = select(func.count()).select_from(model)
    if conditions:
        query = query.where(*conditions)
    return int(session.scalar(query) or 0)


def _encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(row_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not cursor:
        return None
    try:
        raw = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))
        created_at = datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at, uuid.UUID(str(payload["id"]))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_CURSOR", "message": "The operations cursor is invalid"},
        ) from exc


def _page(items: list[Any], *, limit: int, timestamp_attr: str) -> tuple[list[Any], str | None]:
    has_more = len(items) > limit
    visible = items[:limit]
    if not has_more or not visible:
        return visible, None
    last = visible[-1]
    return visible, _encode_cursor(getattr(last, timestamp_attr), last.id)


class CertificationWrite(BaseModel):
    certification_type: str = Field(default="FULL_FUNCTIONAL", min_length=2, max_length=80)
    status: Literal["PASS", "FAIL", "BLOCKED"]
    environment: str = Field(default="unknown", min_length=2, max_length=48)
    git_sha: str | None = Field(default=None, max_length=64)
    evidence: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4000)
    created_by: str | None = Field(default=None, max_length=255)


def _certification_dict(row: OperationsCertification) -> dict[str, Any]:
    return {
        "id": row.id,
        "certification_type": row.certification_type,
        "status": row.status,
        "environment": row.environment,
        "git_sha": row.git_sha,
        "evidence": row.evidence,
        "notes": row.notes,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


@router.get("/summary")
def operations_summary(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    now = utcnow()
    since = now - timedelta(hours=24)
    latest_certification = session.scalar(
        select(OperationsCertification)
        .order_by(OperationsCertification.created_at.desc(), OperationsCertification.id.desc())
        .limit(1)
    )
    run_totals = session.execute(
        select(
            func.coalesce(func.sum(JobIngestionRun.fetched), 0),
            func.coalesce(func.sum(JobIngestionRun.created), 0),
            func.coalesce(func.sum(JobIngestionRun.updated), 0),
            func.coalesce(func.sum(JobIngestionRun.closed), 0),
        ).where(JobIngestionRun.started_at >= since)
    ).one()
    pending_statuses = ["QUEUED", "RETRY_WAIT"]
    oldest_pending_task = session.scalar(
        select(func.min(PostgresTask.available_at)).where(
            PostgresTask.status.in_(pending_statuses)
        )
    )
    last_completed_task = session.scalar(
        select(func.max(PostgresTask.completed_at)).where(
            PostgresTask.status == "COMPLETED"
        )
    )
    live_source_leases = _count(
        session,
        JobSourceRegistry,
        JobSourceRegistry.locked_by.is_not(None),
        JobSourceRegistry.lease_expires_at.is_not(None),
        JobSourceRegistry.lease_expires_at > now,
    )

    return {
        "generated_at": now,
        "runtime": {
            "auth_provider": settings.auth_provider,
            "database_reachable": True,
            "storage_provider": settings.object_storage_provider,
            "storage_configured": settings.storage_runtime_configured,
            "task_queue_provider": settings.task_queue_provider,
            "background_worker_configured": settings.background_worker_configured,
            "supabase_project_configured": bool(settings.resolved_supabase_project_ref),
            "supabase_project_fingerprint": supabase_instance_fingerprint(
                settings.supabase_url
            ),
        },
        "queue": {
            "pending": _count(
                session,
                PostgresTask,
                PostgresTask.status.in_(pending_statuses),
            ),
            "queued": _count(
                session,
                PostgresTask,
                PostgresTask.status == "QUEUED",
            ),
            "retrying": _count(
                session,
                PostgresTask,
                PostgresTask.status == "RETRY_WAIT",
            ),
            "running": _count(
                session,
                PostgresTask,
                PostgresTask.status == "RUNNING",
            ),
            "dead": _count(
                session,
                PostgresTask,
                PostgresTask.status == "DEAD",
            ),
            "completed_24h": _count(
                session,
                PostgresTask,
                PostgresTask.status == "COMPLETED",
                PostgresTask.completed_at >= since,
            ),
            "oldest_pending_at": oldest_pending_task,
            "last_completed_at": last_completed_task,
        },
        "jobs": {
            "total": _count(session, Job),
            "active": _count(session, Job, Job.status == "ACTIVE"),
        },
        "sources": {
            "total": _count(session, JobSourceRegistry),
            "enabled": _count(session, JobSourceRegistry, JobSourceRegistry.enabled.is_(True)),
            "healthy": _count(
                session,
                JobSourceRegistry,
                JobSourceRegistry.health_status == "HEALTHY",
            ),
            "failing": _count(
                session,
                JobSourceRegistry,
                JobSourceRegistry.health_status == "FAILING",
            ),
            "due": _count(
                session,
                JobSourceRegistry,
                JobSourceRegistry.enabled.is_(True),
                JobSourceRegistry.crawl_allowed.is_(True),
                JobSourceRegistry.next_run_at <= now,
            ),
            "live_leases": live_source_leases,
        },
        "ingestion": {
            "runs_24h": _count(session, JobIngestionRun, JobIngestionRun.started_at >= since),
            "failed_24h": _count(
                session,
                JobIngestionRun,
                JobIngestionRun.started_at >= since,
                JobIngestionRun.status.in_(["FAILED", "FAILED_TERMINAL"]),
            ),
            "fetched_24h": int(run_totals[0] or 0),
            "created_24h": int(run_totals[1] or 0),
            "updated_24h": int(run_totals[2] or 0),
            "closed_24h": int(run_totals[3] or 0),
            "pending_source_tasks": _count(
                session,
                TaskOutbox,
                TaskOutbox.event_type == "SOURCE_INGEST",
                TaskOutbox.published_at.is_(None),
            ),
        },
        "certification": {
            "records": _count(session, OperationsCertification),
            "latest": _certification_dict(latest_certification)
            if latest_certification is not None
            else None,
        },
    }


@router.get("/sources")
def operations_sources(
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = select(JobSourceRegistry).order_by(
        JobSourceRegistry.updated_at.desc(),
        JobSourceRegistry.id.desc(),
    )
    decoded = _decode_cursor(cursor)
    if decoded:
        created_at, row_id = decoded
        query = query.where(
            or_(
                JobSourceRegistry.updated_at < created_at,
                and_(
                    JobSourceRegistry.updated_at == created_at,
                    JobSourceRegistry.id < row_id,
                ),
            )
        )
    rows = list(session.scalars(query.limit(limit + 1)))
    visible, next_cursor = _page(rows, limit=limit, timestamp_attr="updated_at")
    return {
        "items": [
            {
                "id": row.id,
                "source_name": row.source_name,
                "source_type": row.source_type,
                "source_identity": row.source_identity,
                "enabled": row.enabled,
                "crawl_allowed": row.crawl_allowed,
                "health_status": row.health_status,
                "last_job_count": row.last_job_count,
                "last_change_count": row.last_change_count,
                "last_success_at": row.last_success_at,
                "last_failure_at": row.last_failure_at,
                "next_run_at": row.next_run_at,
                "updated_at": row.updated_at,
            }
            for row in visible
        ],
        "next_cursor": next_cursor,
    }


@router.post("/sources/{source_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_source_now(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    source = session.get(JobSourceRegistry, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    if not source.enabled or not source.crawl_allowed:
        raise HTTPException(status_code=409, detail="Job source is disabled or policy-blocked")

    now = utcnow()
    lease_token = f"operator-refresh:{uuid.uuid4()}"
    source.next_run_at = now
    task = Task(
        task_type="SOURCE_INGEST",
        payload={
            "source_id": str(source.id),
            "lease_token": lease_token,
            "dispatched_at": now.isoformat(),
        },
        idempotency_key=lease_token,
    )
    outbox = add_task_outbox_event(
        session,
        task=task,
        aggregate_type="job_source_registry",
        aggregate_id=source.id,
    )
    session.flush()
    session.commit()
    return {
        "source_id": source.id,
        "scheduled": True,
        "outbox_id": outbox.id,
        "next_run_at": source.next_run_at,
    }


@router.get("/ingestion")
def ingestion_runs(
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = select(JobIngestionRun).order_by(
        JobIngestionRun.started_at.desc(),
        JobIngestionRun.id.desc(),
    )
    decoded = _decode_cursor(cursor)
    if decoded:
        created_at, row_id = decoded
        query = query.where(
            or_(
                JobIngestionRun.started_at < created_at,
                and_(JobIngestionRun.started_at == created_at, JobIngestionRun.id < row_id),
            )
        )
    rows = list(session.scalars(query.limit(limit + 1)))
    visible, next_cursor = _page(rows, limit=limit, timestamp_attr="started_at")
    return {
        "items": [
            {
                "id": row.id,
                "source_id": row.source_id,
                "source_type": row.source_type,
                "connector": row.connector,
                "source_company": row.source_company,
                "status": row.status,
                "fetched": row.fetched,
                "created": row.created,
                "updated": row.updated,
                "closed": row.closed,
                "failed": row.failed,
                "duration_ms": row.duration_ms,
                "error_category": row.error_category,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
            }
            for row in visible
        ],
        "next_cursor": next_cursor,
    }


@router.post("/certifications", status_code=status.HTTP_201_CREATED)
def create_certification(
    payload: CertificationWrite,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = OperationsCertification(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return _certification_dict(row)


@router.get("/certifications")
def list_certifications(
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = select(OperationsCertification).order_by(
        OperationsCertification.created_at.desc(),
        OperationsCertification.id.desc(),
    )
    decoded = _decode_cursor(cursor)
    if decoded:
        created_at, row_id = decoded
        query = query.where(
            or_(
                OperationsCertification.created_at < created_at,
                and_(
                    OperationsCertification.created_at == created_at,
                    OperationsCertification.id < row_id,
                ),
            )
        )
    rows = list(session.scalars(query.limit(limit + 1)))
    visible, next_cursor = _page(rows, limit=limit, timestamp_attr="created_at")
    return {
        "items": [_certification_dict(row) for row in visible],
        "next_cursor": next_cursor,
    }
