from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.job_quality_models import JobClosureEvidence
from app.models import JobStatusHistory


def closure_detection_metrics(session: Session) -> dict[str, float | int | None]:
    """Measure evidence-to-CLOSED latency from executed closure events only."""
    first_evidence = (
        select(
            JobClosureEvidence.job_id,
            func.min(JobClosureEvidence.observed_at).label("first_observed_at"),
        )
        .where(JobClosureEvidence.applied.is_(True))
        .group_by(JobClosureEvidence.job_id)
        .subquery()
    )
    closures = (
        select(
            JobStatusHistory.job_id,
            func.min(JobStatusHistory.created_at).label("closed_at"),
        )
        .where(JobStatusHistory.to_status == "CLOSED")
        .group_by(JobStatusHistory.job_id)
        .subquery()
    )
    latency = func.extract(
        "epoch",
        closures.c.closed_at - first_evidence.c.first_observed_at,
    )
    values = session.execute(
        select(
            func.count(),
            func.avg(latency),
            func.percentile_cont(0.5).within_group(latency),
            func.percentile_cont(0.95).within_group(latency),
        ).select_from(
            first_evidence.join(closures, closures.c.job_id == first_evidence.c.job_id)
        )
    ).one()
    return {
        "observed_closures": int(values[0] or 0),
        "average_seconds": float(values[1]) if values[1] is not None else None,
        "p50_seconds": float(values[2]) if values[2] is not None else None,
        "p95_seconds": float(values[3]) if values[3] is not None else None,
    }
