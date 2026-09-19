from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.ai.runtime import execute_ai_run
from app.api.career_intelligence_v2 import _queue_run
from app.career_models import AIJobRun, CareerMatch
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.durability_models import TaskOutbox
from app.models import Company, Job, User
from app.postgres_queue_models import PostgresTask
from app.radar_watch_models import RadarBucketTransition, RadarWatch
from app.radar_watch_service import radar_bucket_for_decision

router = APIRouter(prefix="/career-v2/radar", tags=["career radar"])

ENGINE_VERSION = "applyai-hybrid-fit-v2"
# Career V2 currently materializes PRIORITIZE / CONSIDER / STRETCH / SKIP.
# Keep the older aliases here so Radar remains compatible with existing rows.
TOP_DECISIONS = {"PRIORITIZE", "APPLY_NOW", "STRONG"}
WATCH_DECISIONS = {"CONSIDER"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _freshness_at(job: Job) -> datetime:
    candidates = [value for value in (job.posted_at, job.first_seen_at) if value is not None]
    return max(candidates) if candidates else utcnow()


def _freshness_filter(cutoff: datetime):
    # Radar covers roles that are newly posted OR newly discovered by ApplyAI.
    # Using COALESCE would incorrectly hide a newly discovered role when the
    # upstream source carries an older posted_at value.
    return or_(Job.posted_at >= cutoff, Job.first_seen_at >= cutoff)


def _effective_refresh_limit(max_jobs: int, settings: Settings) -> int:
    # In the lean production profile a mutating request drains only a bounded
    # number of PostgreSQL tasks after the handler returns. Never advertise a
    # refresh batch that the request-triggered worker cannot actually consume.
    if settings.task_queue_provider == "postgres" and settings.request_triggered_tasks_enabled:
        return min(max_jobs, settings.request_triggered_task_limit)
    return max_jobs


def _retry_failed_run(
    run: AIJobRun,
    *,
    session: Session,
    settings: Settings,
) -> AIJobRun:
    if run.status != "FAILED":
        return run

    run.status = "QUEUED"
    run.error_code = None
    run.error_summary = None
    add_task_outbox_event(
        session,
        task=Task(
            task_type=run.task_type,
            payload={"run_id": str(run.id)},
            idempotency_key=f"ai-run:{run.id}:{run.attempt_count + 1}",
        ),
        aggregate_type="AIJobRun",
        aggregate_id=run.id,
    )
    session.commit()

    if settings.task_queue_provider == "memory":
        execute_ai_run(run.id, settings)
        session.expire_all()
        return session.get(AIJobRun, run.id) or run
    return run


def _recover_dead_postgres_run(
    run: AIJobRun,
    *,
    session: Session,
    settings: Settings,
) -> AIJobRun:
    """Make an exhausted durable delivery retryable after an explicit Radar refresh.

    Transient AI failures deliberately leave the domain run in QUEUED while the
    PostgreSQL delivery retries. Once that delivery reaches DEAD, the domain run
    otherwise has no state transition that would make a subsequent user refresh
    create work. Re-arming the durable delivery here is safe because we first
    prove there is no active delivery or unpublished outbox event for the run.
    """

    if settings.task_queue_provider != "postgres" or run.status != "QUEUED":
        return run

    key_prefix = f"ai-run:{run.id}"
    active_task = session.scalar(
        select(PostgresTask.id)
        .where(
            PostgresTask.idempotency_key.like(f"{key_prefix}%"),
            PostgresTask.status.in_(("QUEUED", "RETRY_WAIT", "RUNNING")),
        )
        .limit(1)
    )
    if active_task is not None:
        return run

    dead_task = session.scalar(
        select(PostgresTask)
        .where(
            PostgresTask.idempotency_key.like(f"{key_prefix}%"),
            PostgresTask.status == "DEAD",
        )
        .order_by(PostgresTask.created_at.desc(), PostgresTask.id.desc())
        .limit(1)
    )
    if dead_task is None:
        return run

    # An explicit Radar refresh is allowed to re-arm an exhausted durable delivery.
    # If an unpublished outbox event for the same run survived an earlier provider
    # path, suppress it as already delivered by the re-armed Postgres task. Keeping
    # both paths live would risk a second delivery with a different idempotency key.
    pending_outbox = list(
        session.scalars(
            select(TaskOutbox).where(
                TaskOutbox.aggregate_type == "AIJobRun",
                TaskOutbox.aggregate_id == run.id,
                TaskOutbox.event_type == run.task_type,
                TaskOutbox.published_at.is_(None),
                TaskOutbox.status.in_(("PENDING", "CLAIMED")),
            )
        )
    )
    for event in pending_outbox:
        event.status = "PUBLISHED"
        event.published_at = utcnow()
        event.locked_at = None
        event.lock_owner = None
        event.last_error = None

    dead_task.status = "QUEUED"
    dead_task.attempt_count = 0
    dead_task.available_at = utcnow()
    dead_task.leased_at = None
    dead_task.lease_expires_at = None
    dead_task.lease_owner = None
    dead_task.completed_at = None
    dead_task.cancelled_at = None
    dead_task.last_error = None
    run.error_code = None
    run.error_summary = None
    session.commit()
    return run


def _bucket(match: CareerMatch | None) -> str:
    if match is None:
        return "PENDING_JUDGMENT"
    decision = (match.decision or "").upper()
    if decision in TOP_DECISIONS:
        return "TOP_MATCH"
    if decision in WATCH_DECISIONS:
        return "WATCH"
    return "LOW_PRIORITY"


def _bucket_for_decision(decision: str | None) -> str:
    return radar_bucket_for_decision(decision)


def _coverage_counts(
    session: Session,
    *,
    user: User,
    cutoff: datetime,
) -> dict[str, int]:
    match_join = and_(
        CareerMatch.job_id == Job.id,
        CareerMatch.user_id == user.id,
        CareerMatch.engine_version == ENGINE_VERSION,
    )
    grouped = session.execute(
        select(CareerMatch.decision, func.count(Job.id))
        .outerjoin(CareerMatch, match_join)
        .where(Job.status == "ACTIVE", _freshness_filter(cutoff))
        .group_by(CareerMatch.decision)
    ).all()

    counts = {
        "top_match": 0,
        "watch": 0,
        "pending_judgment": 0,
        "low_priority": 0,
    }
    for decision, count in grouped:
        bucket = _bucket_for_decision(decision)
        key = {
            "TOP_MATCH": "top_match",
            "WATCH": "watch",
            "PENDING_JUDGMENT": "pending_judgment",
            "LOW_PRIORITY": "low_priority",
        }[bucket]
        counts[key] += int(count)
    return counts


def _reasons(match: CareerMatch | None) -> list[str]:
    if match is None:
        return ["This fresh role has not been judged against your verified profile yet."]

    reasons: list[str] = []
    for factor in match.factors_json or []:
        if not isinstance(factor, dict):
            continue
        value = (
            factor.get("reason")
            or factor.get("explanation")
            or factor.get("summary")
            or factor.get("label")
        )
        if isinstance(value, str) and value.strip() and value.strip() not in reasons:
            reasons.append(value.strip())
        if len(reasons) == 3:
            break

    if reasons:
        return reasons
    return [
        "ApplyAI classified this role as "
        f"{match.fit_band.lower()} fit with {match.confidence.lower()} confidence."
    ]


def _item(job: Job, company: Company, match: CareerMatch | None) -> dict[str, Any]:
    bucket = _bucket(match)
    return {
        "job_id": str(job.id),
        "title": job.title,
        "company": company.canonical_name,
        "employment_type": job.employment_type,
        "seniority": job.seniority,
        "freshness_at": _freshness_at(job).isoformat(),
        "radar_bucket": bucket,
        "score": match.final_score if match is not None else None,
        "decision": match.decision if match is not None else None,
        "fit_band": match.fit_band if match is not None else None,
        "confidence": match.confidence if match is not None else None,
        "engine_version": match.engine_version if match is not None else None,
        "reasons": _reasons(match),
        "judged_at": match.updated_at.isoformat() if match is not None else None,
    }


@router.get("")
def list_radar(
    limit: int = Query(default=40, ge=1, le=100),
    lookback_days: int = Query(default=14, ge=1, le=90),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    cutoff = utcnow() - timedelta(days=lookback_days)
    match_join = and_(
        CareerMatch.job_id == Job.id,
        CareerMatch.user_id == user.id,
        CareerMatch.engine_version == ENGINE_VERSION,
    )

    rows = list(
        session.execute(
            select(Job, Company, CareerMatch)
            .join(Company, Company.id == Job.company_id)
            .outerjoin(CareerMatch, match_join)
            .where(Job.status == "ACTIVE", _freshness_filter(cutoff))
            .order_by(
                CareerMatch.final_score.desc().nullslast(),
                Job.first_seen_at.desc(),
                Job.posted_at.desc().nullslast(),
                Job.id,
            )
            .limit(limit)
        )
    )
    items = [_item(job, company, match) for job, company, match in rows]
    counts = _coverage_counts(session, user=user, cutoff=cutoff)
    return {
        "items": items,
        "counts": counts,
        "total": sum(counts.values()),
        "returned": len(items),
        "lookback_days": lookback_days,
        "engine_version": ENGINE_VERSION,
        "generated_at": utcnow().isoformat(),
    }


@router.post("/refresh")
def refresh_radar(
    max_jobs: int = Query(default=10, ge=1, le=25),
    lookback_days: int = Query(default=14, ge=1, le=90),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    cutoff = utcnow() - timedelta(days=lookback_days)
    effective_max_jobs = _effective_refresh_limit(max_jobs, settings)
    match_join = and_(
        CareerMatch.job_id == Job.id,
        CareerMatch.user_id == user.id,
        CareerMatch.engine_version == ENGINE_VERSION,
    )
    jobs = list(
        session.scalars(
            select(Job)
            .outerjoin(CareerMatch, match_join)
            .where(
                Job.status == "ACTIVE",
                _freshness_filter(cutoff),
                CareerMatch.id.is_(None),
            )
            .order_by(
                Job.first_seen_at.desc(),
                Job.posted_at.desc().nullslast(),
                Job.id,
            )
            .limit(effective_max_jobs)
        )
    )

    runs = []
    for job in jobs:
        run = _queue_run(
            task_type="AI_DEEP_MATCH",
            job_id=job.id,
            user=user,
            session=session,
            settings=settings,
        )
        if run.status == "FAILED":
            run = _retry_failed_run(run, session=session, settings=settings)
        elif run.status == "QUEUED":
            run = _recover_dead_postgres_run(run, session=session, settings=settings)
        runs.append(
            {
                "run_id": str(run.id),
                "job_id": str(job.id),
                "status": run.status,
            }
        )

    return {
        "requested": max_jobs,
        "scheduled": len(runs),
        "effective_max_jobs": effective_max_jobs,
        "queue_limited": effective_max_jobs < max_jobs,
        "runs": runs,
        "lookback_days": lookback_days,
        "engine_version": ENGINE_VERSION,
    }


class RadarWatchCreate(BaseModel):
    name: str = Field(default="Daily job radar", min_length=1, max_length=120)
    interval_minutes: int = Field(default=1440, ge=60, le=10080)
    lookback_days: int = Field(default=14, ge=1, le=90)
    max_jobs: int = Field(default=5, ge=1, le=10)
    run_immediately: bool = True


class RadarWatchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=60, le=10080)
    lookback_days: int | None = Field(default=None, ge=1, le=90)
    max_jobs: int | None = Field(default=None, ge=1, le=10)


def _watch_payload(watch: RadarWatch) -> dict[str, Any]:
    return {
        "id": str(watch.id),
        "name": watch.name,
        "enabled": watch.enabled,
        "interval_minutes": watch.interval_minutes,
        "lookback_days": watch.lookback_days,
        "max_jobs": watch.max_jobs,
        "next_run_at": watch.next_run_at.isoformat(),
        "last_run_at": watch.last_run_at.isoformat() if watch.last_run_at else None,
        "last_run_status": watch.last_run_status,
        "last_scheduled_jobs": watch.last_scheduled_jobs,
        "last_error": watch.last_error,
        "created_at": watch.created_at.isoformat() if watch.created_at else None,
    }


def _owned_watch(session: Session, user: User, watch_id: uuid.UUID) -> RadarWatch:
    watch = session.scalar(
        select(RadarWatch).where(RadarWatch.id == watch_id, RadarWatch.user_id == user.id)
    )
    if watch is None:
        raise HTTPException(status_code=404, detail="Radar watch not found")
    return watch


@router.get("/watches")
def list_radar_watches(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    rows = list(
        session.scalars(
            select(RadarWatch)
            .where(RadarWatch.user_id == user.id)
            .order_by(RadarWatch.created_at, RadarWatch.id)
        )
    )
    return {"items": [_watch_payload(row) for row in rows]}


@router.post("/watches")
def create_radar_watch(
    body: RadarWatchCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    count = int(
        session.scalar(
            select(func.count()).select_from(RadarWatch).where(RadarWatch.user_id == user.id)
        )
        or 0
    )
    if count >= 5:
        raise HTTPException(status_code=409, detail="A candidate can have at most five Radar watches")
    now = utcnow()
    watch = RadarWatch(
        user_id=user.id,
        name=body.name,
        enabled=True,
        interval_minutes=body.interval_minutes,
        lookback_days=body.lookback_days,
        max_jobs=body.max_jobs,
        next_run_at=now if body.run_immediately else now + timedelta(minutes=body.interval_minutes),
    )
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return _watch_payload(watch)


@router.patch("/watches/{watch_id}")
def update_radar_watch(
    watch_id: uuid.UUID,
    body: RadarWatchUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    watch = _owned_watch(session, user, watch_id)
    values = body.model_dump(exclude_unset=True)
    was_enabled = watch.enabled
    for key, value in values.items():
        setattr(watch, key, value)
    if values.get("enabled") is True and not was_enabled:
        watch.next_run_at = utcnow()
    elif "interval_minutes" in values and watch.enabled:
        watch.next_run_at = utcnow() + timedelta(minutes=watch.interval_minutes)
    session.commit()
    session.refresh(watch)
    return _watch_payload(watch)


@router.post("/watches/{watch_id}/run")
def run_radar_watch_now(
    watch_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    watch = _owned_watch(session, user, watch_id)
    now = utcnow()
    watch.last_run_at = now
    watch.last_run_status = "RUNNING"
    watch.last_error = None
    watch.next_run_at = now + timedelta(minutes=watch.interval_minutes)
    session.commit()
    try:
        result = refresh_radar(
            max_jobs=watch.max_jobs,
            lookback_days=watch.lookback_days,
            user=user,
            session=session,
            settings=settings,
        )
        watch = _owned_watch(session, user, watch_id)
        watch.last_run_status = "SUCCEEDED"
        watch.last_scheduled_jobs = int(result["scheduled"])
        session.commit()
        session.refresh(watch)
        return {"watch": _watch_payload(watch), "refresh": result}
    except Exception as exc:
        watch = _owned_watch(session, user, watch_id)
        watch.last_run_status = "FAILED"
        watch.last_error = f"{type(exc).__name__}:{exc}"[:1000]
        session.commit()
        raise HTTPException(status_code=503, detail="Radar watch could not run") from exc


@router.get("/history")
def list_radar_history(
    limit: int = Query(default=50, ge=1, le=200),
    job_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    statement = select(RadarBucketTransition).where(RadarBucketTransition.user_id == user.id)
    if job_id is not None:
        statement = statement.where(RadarBucketTransition.job_id == job_id)
    rows = list(
        session.scalars(
            statement.order_by(
                RadarBucketTransition.created_at.desc(),
                RadarBucketTransition.id.desc(),
            ).limit(limit)
        )
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "job_id": str(row.job_id),
                "from_bucket": row.from_bucket,
                "to_bucket": row.to_bucket,
                "from_decision": row.from_decision,
                "to_decision": row.to_decision,
                "engine_version": row.engine_version,
                "model_run_id": str(row.model_run_id),
                "entered_top_match": row.to_bucket == "TOP_MATCH" and row.from_bucket != "TOP_MATCH",
                "left_top_match": row.from_bucket == "TOP_MATCH" and row.to_bucket != "TOP_MATCH",
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }
