from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.ai.runtime import execute_ai_run
from app.api.career_intelligence_v2 import _queue_run
from app.career_models import AIJobRun, CareerMatch
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.models import Company, Job, User

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


def _bucket(match: CareerMatch | None) -> str:
    if match is None:
        return "PENDING_JUDGMENT"
    decision = (match.decision or "").upper()
    if decision in TOP_DECISIONS:
        return "TOP_MATCH"
    if decision in WATCH_DECISIONS:
        return "WATCH"
    return "LOW_PRIORITY"


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
    counts = {
        "top_match": sum(item["radar_bucket"] == "TOP_MATCH" for item in items),
        "watch": sum(item["radar_bucket"] == "WATCH" for item in items),
        "pending_judgment": sum(
            item["radar_bucket"] == "PENDING_JUDGMENT" for item in items
        ),
        "low_priority": sum(
            item["radar_bucket"] == "LOW_PRIORITY" for item in items
        ),
    }
    return {
        "items": items,
        "counts": counts,
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
