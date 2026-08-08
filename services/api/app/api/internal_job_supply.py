from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.durability_models import JobIngestionRun
from app.global_job_supply_models import (
    JobDedupCandidate,
    JobSourceCapability,
    OrganizationProfile,
)
from app.job_source_models import JobSourceDiscovery, JobSourceRegistry
from app.jobs.contracts import JobSourceType, SourceTrustLevel
from app.jobs.discovery import request_key_for
from app.jobs.quality import quality_metrics, source_coverage_metrics
from app.jobs.source_capabilities import seed_source_capabilities
from app.jobs.web_security import PublicUrlRejected, validate_public_http_url
from app.models import Company, Job


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


def _source_dict(row: JobSourceRegistry) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "source_type": row.source_type,
        "source_name": row.source_name,
        "source_identity": row.source_identity,
        "base_url": row.base_url,
        "careers_url": row.careers_url,
        "trust_level": row.trust_level,
        "priority": row.priority,
        "enabled": row.enabled,
        "crawl_allowed": row.crawl_allowed,
        "health_status": row.health_status,
        "last_attempt_at": row.last_attempt_at,
        "last_success_at": row.last_success_at,
        "last_failure_at": row.last_failure_at,
        "last_job_count": row.last_job_count,
        "last_change_count": row.last_change_count,
        "consecutive_failures": row.consecutive_failures,
        "last_error_category": row.last_error_category,
        "last_error_summary": row.last_error_summary,
        "crawl_interval_seconds": row.crawl_interval_seconds,
        "next_run_at": row.next_run_at,
        "locked_at": row.locked_at,
        "locked_by": row.locked_by,
        "lease_expires_at": row.lease_expires_at,
        "configuration": row.configuration,
    }


def _capability_dict(row: JobSourceCapability) -> dict[str, Any]:
    operational = dict(row.metadata_json or {})
    return {
        "provider_key": row.provider_key,
        "display_name": row.display_name,
        "access_mode": row.access_mode,
        "implementation_status": row.implementation_status,
        "official_api_available": row.official_api_available,
        "public_feed_available": row.public_feed_available,
        "partner_feed_available": row.partner_feed_available,
        "public_page_access": row.public_page_access,
        "authentication_required": row.authentication_required,
        "requires_credentials": operational.get(
            "requires_credentials", row.authentication_required
        ),
        "requires_partnership": operational.get("requires_partnership", False),
        "robots_policy": row.robots_policy,
        "rate_limit_policy": operational.get("rate_limit_policy"),
        "pagination_strategy": operational.get("pagination_strategy"),
        "supports_delta": operational.get("supports_delta", False),
        "supports_closure_detection": operational.get(
            "supports_closure_detection", False
        ),
        "trust_level": operational.get("trust_level"),
        "allowed_for_automated_ingestion": operational.get(
            "allowed_for_automated_ingestion", False
        ),
        "reason": operational.get("reason"),
        "operator_override": operational.get("operator_override", False),
        "operator_override_at": operational.get("operator_override_at"),
        "recommended_strategy": row.recommended_strategy,
        "documentation_url": row.documentation_url,
        "notes": row.notes,
        "last_verified_at": row.reviewed_at,
    }


class ProviderPatch(BaseModel):
    access_mode: str | None = Field(default=None, max_length=48)
    implementation_status: str | None = Field(default=None, max_length=48)
    allowed_for_automated_ingestion: bool | None = None
    requires_partnership: bool | None = None
    requires_credentials: bool | None = None
    trust_level: str | None = Field(default=None, max_length=48)
    reason: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)


class SourceReclassify(BaseModel):
    source_type: JobSourceType | None = None
    trust_level: SourceTrustLevel | None = None
    crawl_allowed: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=100)


class DedupReviewDecision(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    note: str | None = Field(default=None, max_length=2000)


@router.get("/overview")
def job_supply_overview(
    window_hours: int = Query(default=24, ge=1, le=24 * 90),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    seed_source_capabilities(session)
    session.commit()
    quality = quality_metrics(session, window_hours=window_hours)
    coverage = source_coverage_metrics(session)
    return {
        "status": "MEASURED_REPOSITORY_RUNTIME_STATE",
        "quality": quality,
        "coverage": coverage,
        "provider_capabilities": _count(session, JobSourceCapability),
        "pending_dedup_reviews": _count(
            session, JobDedupCandidate, JobDedupCandidate.status == "PENDING"
        ),
        "generated_at": utcnow(),
    }


@router.get("/summary")
def job_supply_summary(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Compatibility summary retained for existing operator clients."""
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
            select(
                JobSourceRegistry.health_status, func.count(JobSourceRegistry.id)
            ).group_by(JobSourceRegistry.health_status)
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
            select(
                OrganizationProfile.organization_type,
                func.count(OrganizationProfile.id),
            ).group_by(OrganizationProfile.organization_type)
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


@router.get("/providers")
def list_providers(
    implementation_status: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    seed_source_capabilities(session)
    session.commit()
    query = select(JobSourceCapability).order_by(JobSourceCapability.provider_key)
    if implementation_status:
        query = query.where(
            JobSourceCapability.implementation_status == implementation_status
        )
    return [_capability_dict(row) for row in session.scalars(query.limit(limit))]


@router.get("/capabilities")
def list_source_capabilities(
    implementation_status: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return list_providers(implementation_status, limit, session)


@router.patch("/providers/{provider_key}")
def reclassify_provider(
    provider_key: str,
    payload: ProviderPatch,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    seed_source_capabilities(session)
    record = session.scalar(
        select(JobSourceCapability).where(
            JobSourceCapability.provider_key == provider_key.casefold()
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Provider capability not found")
    changes = payload.model_dump(exclude_unset=True)
    metadata = dict(record.metadata_json or {})
    for key in (
        "allowed_for_automated_ingestion",
        "requires_partnership",
        "requires_credentials",
        "trust_level",
        "reason",
    ):
        if key in changes:
            metadata[key] = changes.pop(key)
    for key, value in changes.items():
        setattr(record, key, value)
    override_at = utcnow()
    metadata["operator_override"] = True
    metadata["operator_override_at"] = override_at.isoformat()
    record.metadata_json = metadata
    record.reviewed_at = override_at
    session.commit()
    session.refresh(record)
    return _capability_dict(record)


@router.get("/organizations")
def list_job_supply_organizations(
    organization_type: str | None = None,
    source_status: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = (
        select(OrganizationProfile, Company.canonical_name)
        .join(Company, Company.id == OrganizationProfile.company_id)
        .order_by(OrganizationProfile.priority.desc(), OrganizationProfile.id)
    )
    if organization_type:
        query = query.where(
            OrganizationProfile.organization_type == organization_type.upper()
        )
    if source_status:
        query = query.where(OrganizationProfile.source_status == source_status.upper())
    rows = session.execute(query.limit(limit)).all()
    return [
        {
            "id": row.id,
            "company_id": row.company_id,
            "canonical_name": canonical_name,
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
            "metadata": row.metadata_json,
        }
        for row, canonical_name in rows
    ]


@router.post("/organizations/{organization_id}/discover", status_code=status.HTTP_202_ACCEPTED)
def schedule_organization_discovery(
    organization_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    profile = session.get(OrganizationProfile, organization_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Organization profile not found")
    input_url = profile.careers_url or (
        f"https://{profile.canonical_domain}" if profile.canonical_domain else None
    )
    if not input_url:
        raise HTTPException(
            status_code=409,
            detail="Organization has no verified domain or careers URL",
        )
    try:
        canonical_input = validate_public_http_url(input_url)
    except PublicUrlRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    request_key = request_key_for(None, canonical_input)
    existing = session.scalar(
        select(JobSourceDiscovery).where(JobSourceDiscovery.request_key == request_key)
    )
    if existing is not None and existing.status in {"QUEUED", "RUNNING", "VERIFIED"}:
        return {"discovery_id": existing.id, "status": existing.status, "existing": True}
    if existing is None:
        existing = JobSourceDiscovery(
            company_id=profile.company_id,
            request_key=request_key,
            input_url=canonical_input,
            input_domain=(urlsplit(canonical_input).hostname or "").casefold(),
            status="QUEUED",
            access_policy="UNKNOWN",
            evidence=["job-supply-organization-discovery"],
        )
        session.add(existing)
        session.flush()
    else:
        existing.status = "QUEUED"
        existing.error_category = None
        existing.error_summary = None
        existing.completed_at = None
    profile.source_status = "DISCOVERING"
    add_task_outbox_event(
        session,
        task=Task(
            task_type="SOURCE_DISCOVERY",
            payload={"discovery_id": str(existing.id)},
            idempotency_key=(
                f"organization-source-discovery:{existing.id}:{existing.attempt_count + 1}"
            ),
        ),
        aggregate_type="JOB_SOURCE_DISCOVERY",
        aggregate_id=existing.id,
    )
    session.commit()
    return {"discovery_id": existing.id, "status": existing.status, "existing": False}


@router.get("/sources")
def list_sources(
    health_status: str | None = None,
    source_type: str | None = None,
    enabled: bool | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(JobSourceRegistry).order_by(
        JobSourceRegistry.priority.desc(),
        JobSourceRegistry.source_type,
        JobSourceRegistry.source_name,
    )
    if health_status:
        query = query.where(JobSourceRegistry.health_status == health_status.upper())
    if source_type:
        query = query.where(JobSourceRegistry.source_type == source_type.upper())
    if enabled is not None:
        query = query.where(JobSourceRegistry.enabled.is_(enabled))
    return [_source_dict(row) for row in session.scalars(query.limit(limit))]


@router.get("/failures")
def list_failures(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    failed_sources = list(
        session.scalars(
            select(JobSourceRegistry)
            .where(
                (JobSourceRegistry.consecutive_failures > 0)
                | (JobSourceRegistry.health_status.in_(["DEGRADED", "FAILING"]))
            )
            .order_by(JobSourceRegistry.last_failure_at.desc().nullslast())
            .limit(limit)
        )
    )
    failed_runs = list(
        session.scalars(
            select(JobIngestionRun)
            .where(JobIngestionRun.status.in_(["FAILED", "PARTIAL"]))
            .order_by(JobIngestionRun.started_at.desc())
            .limit(limit)
        )
    )
    return {
        "sources": [_source_dict(row) for row in failed_sources],
        "runs": [
            {
                "id": row.id,
                "source_id": row.source_id,
                "source_type": row.source_type,
                "connector": row.connector,
                "status": row.status,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "error_category": row.error_category,
                "error_summary": row.error_summary,
                "failed": row.failed,
            }
            for row in failed_runs
        ],
    }


@router.get("/runs")
def list_runs(
    run_status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(JobIngestionRun).order_by(JobIngestionRun.started_at.desc())
    if run_status:
        query = query.where(JobIngestionRun.status == run_status.upper())
    rows = list(session.scalars(query.limit(limit)))
    return [
        {
            "id": row.id,
            "source_id": row.source_id,
            "source_type": row.source_type,
            "connector": row.connector,
            "source_company": row.source_company,
            "status": row.status,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "duration_ms": row.duration_ms,
            "fetched": row.fetched,
            "valid": row.valid,
            "invalid": row.invalid,
            "created": row.created,
            "updated": row.updated,
            "unchanged": row.unchanged,
            "deduplicated": row.deduplicated,
            "failed": row.failed,
            "stale": row.stale,
            "closed": row.closed,
            "error_category": row.error_category,
            "error_summary": row.error_summary,
        }
        for row in rows
    ]


@router.get("/dedup-review")
def list_dedup_review(
    review_status: str = Query(default="PENDING", max_length=32),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = list(
        session.scalars(
            select(JobDedupCandidate)
            .where(JobDedupCandidate.status == review_status.upper())
            .order_by(JobDedupCandidate.confidence_bps.desc(), JobDedupCandidate.created_at)
            .limit(limit)
        )
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        left = session.get(Job, row.left_job_id)
        right = session.get(Job, row.right_job_id)
        result.append(
            {
                "id": row.id,
                "left_job": (
                    {"id": left.id, "title": left.title, "company_id": left.company_id}
                    if left
                    else None
                ),
                "right_job": (
                    {"id": right.id, "title": right.title, "company_id": right.company_id}
                    if right
                    else None
                ),
                "reason": row.reason,
                "confidence_bps": row.confidence_bps,
                "evidence": row.evidence,
                "status": row.status,
                "created_at": row.created_at,
                "reviewed_at": row.reviewed_at,
            }
        )
    return result


@router.post("/dedup-review/{candidate_id}/decision")
def decide_dedup_review(
    candidate_id: uuid.UUID,
    payload: DedupReviewDecision,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    candidate = session.get(JobDedupCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Dedup candidate not found")
    evidence = dict(candidate.evidence or {})
    if payload.note:
        evidence["operator_note"] = payload.note
    candidate.evidence = evidence
    candidate.status = payload.decision
    candidate.reviewed_at = utcnow()
    session.commit()
    return {
        "id": candidate.id,
        "status": candidate.status,
        "reviewed_at": candidate.reviewed_at,
        "canonical_merge_performed": False,
    }


@router.get("/quality")
def get_job_supply_quality(
    window_hours: int = Query(default=24, ge=1, le=24 * 90),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return {
        "quality": quality_metrics(session, window_hours=window_hours),
        "coverage": source_coverage_metrics(session),
    }


@router.get("/sources/{source_id}")
def get_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    source = session.get(JobSourceRegistry, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    return _source_dict(source)


@router.post("/sources/{source_id}/enable")
def enable_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    source = session.get(JobSourceRegistry, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    source.enabled = True
    if source.crawl_allowed and source.health_status in {"DISABLED", "BLOCKED"}:
        source.health_status = "HEALTHY"
    source.consecutive_failures = 0
    session.commit()
    return _source_dict(source)


@router.post("/sources/{source_id}/disable")
def disable_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    source = session.get(JobSourceRegistry, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    source.enabled = False
    source.health_status = "DISABLED"
    source.locked_at = None
    source.locked_by = None
    source.lease_expires_at = None
    session.commit()
    return _source_dict(source)


@router.post("/sources/{source_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    source = session.get(JobSourceRegistry, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    if not source.enabled or not source.crawl_allowed:
        raise HTTPException(status_code=409, detail="Job source is disabled or policy-blocked")
    source.next_run_at = utcnow()
    session.commit()
    return {"source_id": source.id, "scheduled": True, "next_run_at": source.next_run_at}


@router.patch("/sources/{source_id}/reclassify")
def reclassify_source(
    source_id: uuid.UUID,
    payload: SourceReclassify,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    source = session.get(JobSourceRegistry, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    changes = payload.model_dump(exclude_unset=True)
    source_type = changes.pop("source_type", None)
    trust_level = changes.pop("trust_level", None)
    if source_type is not None:
        source.source_type = source_type.value
    if trust_level is not None:
        source.trust_level = trust_level.value
    for key, value in changes.items():
        setattr(source, key, value)
    if source.crawl_allowed is False:
        source.health_status = "BLOCKED"
        source.locked_at = None
        source.locked_by = None
        source.lease_expires_at = None
    session.commit()
    return _source_dict(source)
