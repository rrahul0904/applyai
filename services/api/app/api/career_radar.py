from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
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
    pending_outbox = session.scalar(
        select(TaskOutbox.id)
        .where(
            TaskOutbox.aggregate_type == "AIJobRun",
            TaskOutbox.aggregate_id == run.id,
            TaskOutbox.event_type == run.task_type,
            TaskOutbox.published_at.is_(None),
            TaskOutbox.status.in_(("PENDING", "CLAIMED")),
        )
        .limit(1)
    )
    if active_task is not None or pending_outbox is not None:
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
    if decision is None:
        return "PENDING_JUDGMENT"
    normalized = decision.upper()
    if normalized in TOP_DECISIONS:
        return "TOP_MATCH"
    if normalized in WATCH_DECISIONS:
        return "WATCH"
    return "LOW_PRIORITY"


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
