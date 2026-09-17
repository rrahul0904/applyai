from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.career_intelligence_v2 import _queue_run
from app.career_models import CareerMatch
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models import Company, Job, User

router = APIRouter(prefix="/career-v2/radar", tags=["career radar"])

ENGINE_VERSION = "applyai-hybrid-fit-v2"
TOP_DECISIONS = {"APPLY_NOW", "STRONG"}
WATCH_DECISIONS = {"CONSIDER"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _freshness_at(job: Job) -> datetime:
    return job.posted_at or job.first_seen_at


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
    freshness = func.coalesce(Job.posted_at, Job.first_seen_at)
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
            .where(Job.status == "ACTIVE", freshness >= cutoff)
            .order_by(
                CareerMatch.final_score.desc().nullslast(),
                freshness.desc(),
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
    freshness = func.coalesce(Job.posted_at, Job.first_seen_at)
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
                freshness >= cutoff,
                CareerMatch.id.is_(None),
            )
            .order_by(freshness.desc(), Job.id)
            .limit(max_jobs)
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
        runs.append(
            {
                "run_id": str(run.id),
                "job_id": str(job.id),
                "status": run.status,
            }
        )

    return {
        "scheduled": len(runs),
        "runs": runs,
        "lookback_days": lookback_days,
        "engine_version": ENGINE_VERSION,
    }
