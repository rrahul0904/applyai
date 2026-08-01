from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.durability_models import JobIngestionRun
from app.job_quality_models import IngestionCostObservation, JobApplyUrlCheck
from app.job_source_models import JobSourceDiscovery, JobSourceRegistry
from app.models import (
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobSource,
    JobSourceLink,
    JobStatusHistory,
    RawJobPosting,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _decimal(value) -> float | None:
    if value is None:
        return None
    return float(value)


def quality_metrics(session: Session, *, window_hours: int = 24) -> dict:
    since = utcnow() - timedelta(hours=window_hours)
    canonical_active = session.scalar(
        select(func.count(Job.id)).where(Job.status == "ACTIVE")
    ) or 0
    source_postings = session.scalar(select(func.count(JobSource.id))) or 0
    total_jobs = session.scalar(select(func.count(Job.id))) or 0
    total_raw = session.scalar(select(func.count(RawJobPosting.id))) or 0
    invalid_raw = session.scalar(
        select(func.count(RawJobPosting.id)).where(
            RawJobPosting.normalization_status.in_(["INVALID", "QUARANTINED"])
        )
    ) or 0
    quarantined = session.scalar(
        select(func.count(JobSourceDiscovery.id)).where(
            JobSourceDiscovery.status.in_(["REJECTED", "BLOCKED"])
        )
    ) or 0
    discoveries = session.scalar(select(func.count(JobSourceDiscovery.id))) or 0
    jobs_with_salary = session.scalar(
        select(func.count(distinct(JobCompensation.job_id)))
    ) or 0
    jobs_with_location = session.scalar(
        select(func.count(distinct(JobLocation.job_id))).where(
            JobLocation.location_text != "Location not specified"
        )
    ) or 0

    new_jobs = session.scalar(
        select(func.count(Job.id)).where(Job.created_at >= since)
    ) or 0
    updated_jobs = session.scalar(
        select(func.count(JobStatusHistory.id)).where(
            JobStatusHistory.created_at >= since,
            JobStatusHistory.reason == "SOURCE_SEEN_AGAIN",
        )
    ) or 0
    closed_jobs = session.scalar(
        select(func.count(JobStatusHistory.id)).where(
            JobStatusHistory.created_at >= since,
            JobStatusHistory.to_status == "CLOSED",
        )
    ) or 0

    run_stats = session.execute(
        select(
            func.count(JobIngestionRun.id),
            func.sum(case((JobIngestionRun.status == "FAILED", 1), else_=0)),
            func.percentile_cont(0.5).within_group(JobIngestionRun.duration_ms),
            func.percentile_cont(0.95).within_group(JobIngestionRun.duration_ms),
        ).where(JobIngestionRun.started_at >= since)
    ).one()
    run_count = int(run_stats[0] or 0)
    failed_runs = int(run_stats[1] or 0)

    latest_checks = (
        select(
            JobApplyUrlCheck.job_source_id,
            func.max(JobApplyUrlCheck.checked_at).label("checked_at"),
        )
        .group_by(JobApplyUrlCheck.job_source_id)
        .subquery()
    )
    latest_statuses = list(
        session.scalars(
            select(JobApplyUrlCheck.status)
            .join(
                latest_checks,
                (latest_checks.c.job_source_id == JobApplyUrlCheck.job_source_id)
                & (latest_checks.c.checked_at == JobApplyUrlCheck.checked_at),
            )
        )
    )
    valid_checks = sum(status in {"VALID", "REDIRECTED"} for status in latest_statuses)

    average_verification_age = session.scalar(
        select(
            func.avg(
                func.extract("epoch", utcnow() - JobSource.last_seen_at)
            )
        ).where(JobSource.last_seen_at.is_not(None))
    )

    cost = session.execute(
        select(
            func.sum(IngestionCostObservation.worker_seconds),
            func.sum(IngestionCostObservation.network_bytes),
            func.sum(IngestionCostObservation.source_postings),
            func.sum(IngestionCostObservation.estimated_cost_usd),
        ).where(IngestionCostObservation.recorded_at >= since)
    ).one()

    return {
        "window_hours": window_hours,
        "canonical_active_jobs": canonical_active,
        "canonical_total_jobs": total_jobs,
        "source_postings": source_postings,
        "canonical_source_ratio": (
            round(canonical_active / source_postings, 6) if source_postings else None
        ),
        "new_jobs": new_jobs,
        "updated_jobs": updated_jobs,
        "closed_jobs": closed_jobs,
        "new_jobs_per_hour": round(new_jobs / window_hours, 6),
        "updated_jobs_per_hour": round(updated_jobs / window_hours, 6),
        "closed_jobs_per_hour": round(closed_jobs / window_hours, 6),
        "duplicate_percentage": (
            round(max(0, source_postings - total_jobs) / source_postings * 100, 4)
            if source_postings
            else 0.0
        ),
        "invalid_percentage": round(invalid_raw / total_raw * 100, 4) if total_raw else 0.0,
        "quarantine_percentage": (
            round(quarantined / discoveries * 100, 4) if discoveries else 0.0
        ),
        "apply_url_validity_percentage": (
            round(valid_checks / len(latest_statuses) * 100, 4)
            if latest_statuses
            else None
        ),
        "salary_coverage_percentage": (
            round(jobs_with_salary / total_jobs * 100, 4) if total_jobs else 0.0
        ),
        "location_coverage_percentage": (
            round(jobs_with_location / total_jobs * 100, 4) if total_jobs else 0.0
        ),
        "average_verification_age_seconds": _decimal(average_verification_age),
        "ingestion_duration_p50_ms": _decimal(run_stats[2]),
        "ingestion_duration_p95_ms": _decimal(run_stats[3]),
        "source_failure_rate_percentage": (
            round(failed_runs / run_count * 100, 4) if run_count else 0.0
        ),
        "run_count": run_count,
        "measured_worker_seconds": _decimal(cost[0]) or 0.0,
        "measured_network_bytes": int(cost[1] or 0),
        "measured_source_postings": int(cost[2] or 0),
        "measured_estimated_cost_usd": _decimal(cost[3]),
    }


def source_coverage_metrics(session: Session) -> dict:
    by_type = dict(
        session.execute(
            select(JobSourceRegistry.source_type, func.count(JobSourceRegistry.id)).group_by(
                JobSourceRegistry.source_type
            )
        ).all()
    )
    successful_source_ids = set(
        session.scalars(
            select(JobIngestionRun.source_id).where(
                JobIngestionRun.status == "COMPLETED",
                JobIngestionRun.source_id.is_not(None),
            )
        )
    )
    return {
        "companies_total": session.scalar(select(func.count(Company.id))) or 0,
        "companies_discovered": session.scalar(
            select(func.count(distinct(JobSourceDiscovery.company_id))).where(
                JobSourceDiscovery.company_id.is_not(None)
            )
        )
        or 0,
        "companies_with_career_sites": session.scalar(
            select(func.count(distinct(JobSourceRegistry.company_id))).where(
                JobSourceRegistry.company_id.is_not(None),
                JobSourceRegistry.careers_url.is_not(None),
            )
        )
        or 0,
        "companies_with_detected_ats": session.scalar(
            select(func.count(distinct(JobSourceDiscovery.company_id))).where(
                JobSourceDiscovery.company_id.is_not(None),
                JobSourceDiscovery.detected_provider.is_not(None),
            )
        )
        or 0,
        "companies_with_active_source": session.scalar(
            select(func.count(distinct(JobSourceRegistry.company_id))).where(
                JobSourceRegistry.company_id.is_not(None),
                JobSourceRegistry.enabled.is_(True),
            )
        )
        or 0,
        "sources_with_successful_ingestion": len(successful_source_ids),
        "sources_by_type": {key: int(value) for key, value in by_type.items()},
    }
