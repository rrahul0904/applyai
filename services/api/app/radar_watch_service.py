from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.career_models import CareerMatch
from app.radar_watch_models import RadarBucketTransition

TOP_DECISIONS = {"PRIORITIZE", "APPLY_NOW", "STRONG"}
WATCH_DECISIONS = {"CONSIDER"}


def radar_bucket_for_decision(decision: str | None) -> str:
    if decision is None:
        return "PENDING_JUDGMENT"
    normalized = decision.upper()
    if normalized in TOP_DECISIONS:
        return "TOP_MATCH"
    if normalized in WATCH_DECISIONS:
        return "WATCH"
    return "LOW_PRIORITY"


def record_radar_bucket_transition(
    session: Session,
    *,
    match: CareerMatch,
    previous_decision: str | None,
    model_run_id: uuid.UUID,
) -> RadarBucketTransition | None:
    from_bucket = radar_bucket_for_decision(previous_decision)
    to_bucket = radar_bucket_for_decision(match.decision)
    if from_bucket == to_bucket:
        return None

    existing = session.scalar(
        select(RadarBucketTransition).where(
            RadarBucketTransition.user_id == match.user_id,
            RadarBucketTransition.job_id == match.job_id,
            RadarBucketTransition.engine_version == match.engine_version,
            RadarBucketTransition.model_run_id == model_run_id,
        )
    )
    if existing is not None:
        return existing

    row = RadarBucketTransition(
        user_id=match.user_id,
        job_id=match.job_id,
        match_id=match.id,
        model_run_id=model_run_id,
        engine_version=match.engine_version,
        from_bucket=from_bucket,
        to_bucket=to_bucket,
        from_decision=previous_decision,
        to_decision=match.decision,
    )
    session.add(row)
    return row
