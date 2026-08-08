from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.durability_models import JobIngestionRun
from app.global_job_supply_models import JobSourceCapability, OrganizationProfile
from app.job_source_models import JobSourceRegistry
from app.models import Job


router = APIRouter(
    prefix="/internal/job-supply",
    tags=["internal-job-supply"],
    dependencies=[Depends(require_internal_api)],
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _count(session: Session, model, *conditions) -> int:
    query = select(func.count()).select_from(model)
    if conditions:
        query = query.where(*conditions)
    return int(session.scalar(query) or 0)


@router.get("/summary")
def job_supply_summary(session: Session = Depends(get_session)) -> dict[str, Any]:
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    run_totals = session.execute(
        select(
            func.coalesce(func.sum(JobIngestionRun.fetched), 0),
            func.coalesce(func.sum(JobIngestionRun.created), 0),
            func.coalesce(func.sum(JobIngestionRun.updated), 0),
            func.coalesce(func.sum(JobIngestionRun.closed), 0),
            func.coalesce(func.sum(JobIngestionRun.deduplicated), 0),
            func.coalesce(func.sum(JobIngestionRun.invalid), 0),
            func.coalesce(func.avg(JobIngestionRun.duration_ms), 0),
        ).where(JobIngestionRun.started_at >= today)
    ).one()

    health_rows = dict(
        session.execute(
            select(JobSourceRegistry.health_status, func.count(JobSourceRegistry.id)).group_by(
                JobSourceRegistry.health_status
            )
        ).all()
    )
    provider_rows = dict(
        session.execute(
            select(JobSourceRegistry.source_type, func.count(JobSourceRegistry.id)).group_by(
                JobSourceRegistry.source_type
            )
        ).all()
    )
    organization_rows = dict(
        session.execute(
            select(OrganizationProfile.organization_type, func.count(OrganizationProfile.id)).group_by(
                OrganizationProfile.organization_type
            )
        ).all()
    )
    capability_rows = dict(
        session.execute(
            select(
                JobSourceCapability.implementation_status,
                func.count(JobSourceCapability.id),
            ).group_by(JobSourceCapability.implementation_status)
        ).all()
    )

    active_sources = _count(
        session,
        JobSourceRegistry,
        JobSourceRegistry.enabled.is_(True),
        JobSourceRegistry.crawl_allowed.is_(True),
    )
    return {
        "organizations": _count(session, OrganizationProfile),
        "organizations_by_type": organization_rows,
        "sources": _count(session, JobSourceRegistry),
        "active_sources": active_sources,
        "blocked_sources": _count(
            session,
            JobSourceRegistry,
            JobSourceRegistry.crawl_allowed.is_(False),
        ),
        "source_health": health_rows,
        "sources_by_provider": provider_rows,
        "provider_capabilities": capability_rows,
        "active_jobs": _count(session, Job, Job.status == "ACTIVE"),
        "jobs_fetched_today": int(run_totals[0] or 0),
        "jobs_created_today": int(run_totals[1] or 0),
        "jobs_updated_today": int(run_totals[2] or 0),
        "jobs_closed_today": int(run_totals[3] or 0),
        "duplicates_today": int(run_totals[4] or 0),
        "quarantined_or_invalid_today": int(run_totals[5] or 0),
        "average_ingestion_duration_ms_today": int(run_totals[6] or 0),
        "generated_at": utcnow(),
    }


@router.get("/capabilities")
def list_source_capabilities(
    implementation_status: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(JobSourceCapability).order_by(JobSourceCapability.provider_key)
    if implementation_status:
        query = query.where(JobSourceCapability.implementation_status == implementation_status)
    rows = list(session.scalars(query.limit(limit)))
    return [
        {
            "provider_key": row.provider_key,
            "display_name": row.display_name,
            "access_mode": row.access_mode,
            "implementation_status": row.implementation_status,
            "official_api_available": row.official_api_available,
            "public_feed_available": row.public_feed_available,
            "partner_feed_available": row.partner_feed_available,
            "public_page_access": row.public_page_access,
            "authentication_required": row.authentication_required,
            "robots_policy": row.robots_policy,
            "recommended_strategy": row.recommended_strategy,
            "documentation_url": row.documentation_url,
            "reviewed_at": row.reviewed_at,
        }
        for row in rows
    ]


@router.get("/organizations")
def list_job_supply_organizations(
    organization_type: str | None = None,
    source_status: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(OrganizationProfile).order_by(
        OrganizationProfile.priority.desc(), OrganizationProfile.id
    )
    if organization_type:
        query = query.where(OrganizationProfile.organization_type == organization_type.upper())
    if source_status:
        query = query.where(OrganizationProfile.source_status == source_status.upper())
    rows = list(session.scalars(query.limit(limit)))
    return [
        {
            "id": row.id,
            "company_id": row.company_id,
            "canonical_domain": row.canonical_domain,
            "organization_type": row.organization_type,
            "industry": row.industry,
            "country_code": row.country_code,
            "state_region": row.state_region,
            "priority": row.priority,
            "careers_url": row.careers_url,
            "ats_provider": row.ats_provider,
            "source_status": row.source_status,
            "dataset_provenance": row.dataset_provenance,
            "last_verified_at": row.last_verified_at,
        }
        for row in rows
    ]
