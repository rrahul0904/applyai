from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.durability_models import JobIngestionRun
from app.global_job_supply_models import OrganizationProfile
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


def _count(session: Session, model, *conditions) -> int:
    query = select(func.count()).select_from(model)
    if conditions:
        query = query.where(*conditions)
    return int(session.scalar(query) or 0)


def _freshness_buckets(session: Session) -> dict[str, int]:
    now = utcnow()
    buckets = {
        "lt_3h": 0,
        "lt_6h": 0,
        "lt_12h": 0,
        "lt_24h": 0,
        "gte_24h": 0,
    }
    rows = list(
        session.scalars(
            select(Job.last_seen_at).where(
                Job.status.in_(["ACTIVE", "UNKNOWN", "STALE"]),
                Job.last_seen_at.is_not(None),
            )
        )
    )
    for observed_at in rows:
        age = now - observed_at
        if age < timedelta(hours=3):
            buckets["lt_3h"] += 1
        elif age < timedelta(hours=6):
            buckets["lt_6h"] += 1
        elif age < timedelta(hours=12):
            buckets["lt_12h"] += 1
        elif age < timedelta(hours=24):
            buckets["lt_24h"] += 1
        else:
            buckets["gte_24h"] += 1
    return buckets


def _source_authority_counts(session: Session) -> dict[str, int]:
    rows = list(
        session.execute(
            select(JobSourceLink.is_primary, JobSource.checkpoint)
            .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
            .where(JobSourceLink.is_primary.is_(True))
        ).all()
    )
    counts: Counter[str] = Counter()
    for _is_primary, checkpoint in rows:
        checkpoint = dict(checkpoint or {})
        metadata = checkpoint.get("source_metadata") or {}
        trust = (
            metadata.get("trust_level")
            if isinstance(metadata, dict)
            else None
        )
        counts[str(trust or checkpoint.get("source_type") or "UNKNOWN")] += 1
    return dict(sorted(counts.items()))


def quality_metrics(session: Session, *, window_hours: int = 24) -> dict:
    since = utcnow() - timedelta(hours=window_hours)
    canonical_active = _count(session, Job, Job.status == "ACTIVE")
    canonical_closed = _count(session, Job, Job.status == "CLOSED")
    canonical_stale = _count(session, Job, Job.status == "STALE")
    source_postings = _count(session, JobSource)
    total_jobs = _count(session, Job)
    total_raw = _count(session, RawJobPosting)
    invalid_raw = _count(
        session,
        RawJobPosting,
        RawJobPosting.normalization_status.in_(["INVALID", "QUARANTINED"]),
    )
    quarantined = _count(
        session,
        JobSourceDiscovery,
        JobSourceDiscovery.status.in_(["REJECTED", "BLOCKED"]),
    )
    discoveries = _count(session, JobSourceDiscovery)
    jobs_with_salary = int(
        session.scalar(select(func.count(distinct(JobCompensation.job_id)))) or 0
    )
    jobs_with_location = int(
        session.scalar(
            select(func.count(distinct(JobLocation.job_id))).where(
                JobLocation.location_text != "Location not specified"
            )
        )
        or 0
    )

    new_jobs = _count(session, Job, Job.created_at >= since)
    updated_jobs = _count(
        session,
        JobStatusHistory,
        JobStatusHistory.created_at >= since,
        JobStatusHistory.reason == "SOURCE_SEEN_AGAIN",
    )
    closed_jobs = _count(
        session,
        JobStatusHistory,
        JobStatusHistory.created_at >= since,
        JobStatusHistory.to_status == "CLOSED",
    )
    reopened_jobs = _count(
        session,
        JobStatusHistory,
        JobStatusHistory.created_at >= since,
        JobStatusHistory.from_status == "CLOSED",
        JobStatusHistory.to_status.in_(["ACTIVE", "UNKNOWN"]),
    )

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
            select(JobApplyUrlCheck.status).join(
                latest_checks,
                (latest_checks.c.job_source_id == JobApplyUrlCheck.job_source_id)
                & (latest_checks.c.checked_at == JobApplyUrlCheck.checked_at),
            )
        )
    )
    valid_checks = sum(status in {"VALID", "REDIRECTED"} for status in latest_statuses)

    average_verification_age = session.scalar(
        select(
            func.avg(func.extract("epoch", utcnow() - JobSource.last_seen_at))
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

    cross_source_jobs = int(
        session.scalar(
            select(func.count()).select_from(
                select(JobSourceLink.job_id)
                .group_by(JobSourceLink.job_id)
                .having(func.count(JobSourceLink.id) > 1)
                .subquery()
            )
        )
        or 0
    )
    orphan_source_jobs = int(
        session.scalar(
            select(func.count(JobSource.id))
            .outerjoin(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
            .where(JobSourceLink.id.is_(None))
        )
        or 0
    )

    source_health = dict(
        session.execute(
            select(JobSourceRegistry.health_status, func.count(JobSourceRegistry.id)).group_by(
                JobSourceRegistry.health_status
            )
        ).all()
    )
    sources_by_type = dict(
        session.execute(
            select(JobSourceRegistry.source_type, func.count(JobSourceRegistry.id)).group_by(
                JobSourceRegistry.source_type
            )
        ).all()
    )
    organizations_by_type = dict(
        session.execute(
            select(
                OrganizationProfile.organization_type,
                func.count(OrganizationProfile.id),
            ).group_by(OrganizationProfile.organization_type)
        ).all()
    )

    source_enabled = _count(
        session,
        JobSourceRegistry,
        JobSourceRegistry.enabled.is_(True),
    )
    source_blocked = _count(
        session,
        JobSourceRegistry,
        JobSourceRegistry.crawl_allowed.is_(False),
    )

    return {
        "window_hours": window_hours,
        "organizations_total": _count(session, OrganizationProfile),
        "organizations_with_domains": _count(
            session,
            OrganizationProfile,
            OrganizationProfile.canonical_domain.is_not(None),
        ),
        "organizations_with_career_sites": _count(
            session,
            OrganizationProfile,
            OrganizationProfile.careers_url.is_not(None),
        ),
        "organizations_with_detected_ats": _count(
            session,
            OrganizationProfile,
            OrganizationProfile.ats_provider.is_not(None),
        ),
        "organizations_by_type": {key: int(value) for key, value in organizations_by_type.items()},
        "sources_total": _count(session, JobSourceRegistry),
        "sources_enabled": source_enabled,
        "sources_healthy": int(source_health.get("HEALTHY", 0)),
        "sources_blocked": source_blocked + int(source_health.get("BLOCKED", 0)),
        "sources_failing": int(source_health.get("FAILING", 0)),
        "sources_by_type": {key: int(value) for key, value in sources_by_type.items()},
        "raw_jobs_seen": total_raw,
        "canonical_active_jobs": canonical_active,
        "canonical_closed_jobs": canonical_closed,
        "canonical_stale_jobs": canonical_stale,
        "canonical_total_jobs": total_jobs,
        "source_postings": source_postings,
        "canonical_source_ratio": (
            round(canonical_active / source_postings, 6) if source_postings else None
        ),
        "new_jobs": new_jobs,
        "updated_jobs": updated_jobs,
        "closed_jobs": closed_jobs,
        "reopened_jobs": reopened_jobs,
        "new_jobs_per_hour": round(new_jobs / window_hours, 6),
        "updated_jobs_per_hour": round(updated_jobs / window_hours, 6),
        "closed_jobs_per_hour": round(closed_jobs / window_hours, 6),
        "duplicate_percentage": (
            round(max(0, source_postings - total_jobs) / source_postings * 100, 4)
            if source_postings
            else 0.0
        ),
        "cross_source_jobs": cross_source_jobs,
        "orphan_source_jobs": orphan_source_jobs,
        "invalid_percentage": round(invalid_raw / total_raw * 100, 4) if total_raw else 0.0,
        "quarantine_percentage": (
            round(quarantined / discoveries * 100, 4) if discoveries else 0.0
        ),
        "apply_url_validity_percentage": (
            round(valid_checks / len(latest_statuses) * 100, 4)
            if latest_statuses
            else None
        ),
        "apply_urls_checked": len(latest_statuses),
        "salary_coverage_percentage": (
            round(jobs_with_salary / total_jobs * 100, 4) if total_jobs else 0.0
        ),
        "location_coverage_percentage": (
            round(jobs_with_location / total_jobs * 100, 4) if total_jobs else 0.0
        ),
        "freshness": _freshness_buckets(session),
        "jobs_by_source_authority": _source_authority_counts(session),
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
        "requests_per_1000_jobs": None,
        "worker_seconds_per_1000_jobs": (
            round(float(cost[0] or 0) / int(cost[2] or 0) * 1000, 6)
            if int(cost[2] or 0) > 0
            else None
        ),
        "generated_at": utcnow(),
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
    organizations_by_type = dict(
        session.execute(
            select(
                OrganizationProfile.organization_type,
                func.count(OrganizationProfile.id),
            ).group_by(OrganizationProfile.organization_type)
        ).all()
    )
    return {
        "companies_total": _count(session, Company),
        "organizations_total": _count(session, OrganizationProfile),
        "organizations_by_type": {key: int(value) for key, value in organizations_by_type.items()},
        "companies_discovered": int(
            session.scalar(
                select(func.count(distinct(JobSourceDiscovery.company_id))).where(
                    JobSourceDiscovery.company_id.is_not(None)
                )
            )
            or 0
        ),
        "companies_with_career_sites": int(
            session.scalar(
                select(func.count(distinct(JobSourceRegistry.company_id))).where(
                    JobSourceRegistry.company_id.is_not(None),
                    JobSourceRegistry.careers_url.is_not(None),
                )
            )
            or 0
        ),
        "companies_with_detected_ats": int(
            session.scalar(
                select(func.count(distinct(JobSourceDiscovery.company_id))).where(
                    JobSourceDiscovery.company_id.is_not(None),
                    JobSourceDiscovery.detected_provider.is_not(None),
                )
            )
            or 0
        ),
        "companies_with_active_source": int(
            session.scalar(
                select(func.count(distinct(JobSourceRegistry.company_id))).where(
                    JobSourceRegistry.company_id.is_not(None),
                    JobSourceRegistry.enabled.is_(True),
                )
            )
            or 0
        ),
        "sources_with_successful_ingestion": len(successful_source_ids),
        "sources_by_type": {key: int(value) for key, value in by_type.items()},
    }
