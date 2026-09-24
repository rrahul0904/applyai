from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task, supports_task_type
from app.job_radar_models import JobScan, JobScanMatch, JobSearchProfile
from app.job_radar_service import PROVIDER_NAME, SCORING_VERSION, build_query_plan, run_job_scan
from app.models import ResumeVersion, User

router = APIRouter(prefix="/job-radar", tags=["job radar"])


class JobSearchProfileInput(BaseModel):
    resume_version_id: uuid.UUID | None = None
    target_titles: list[str] = Field(min_length=1, max_length=8)
    skills: list[str] = Field(default_factory=list, max_length=40)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    seniority_preferences: list[str] = Field(default_factory=list, max_length=8)
    preferred_locations: list[str] = Field(default_factory=list, max_length=12)
    remote_policy: Literal["ANY", "REMOTE", "HYBRID", "ONSITE"] = "ANY"
    salary_min: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_currency: str = Field(default="USD", min_length=3, max_length=3)


class JobScanRequest(BaseModel):
    max_queries: int = Field(default=5, ge=1, le=8)
    per_query_limit: int = Field(default=25, ge=1, le=50)
    top_k: int = Field(default=10, ge=1, le=50)


def _clean_values(values: list[str], *, maximum_length: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.split()).strip()[:maximum_length]
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        result.append(cleaned)
    return result


def _profile_payload(profile: JobSearchProfile) -> dict:
    return {
        "id": str(profile.id),
        "resume_version_id": str(profile.resume_version_id) if profile.resume_version_id else None,
        "target_titles": profile.target_titles,
        "skills": profile.skills,
        "years_experience": profile.years_experience,
        "seniority_preferences": profile.seniority_preferences,
        "preferred_locations": profile.preferred_locations,
        "remote_policy": profile.remote_policy,
        "salary_min": profile.salary_min,
        "salary_currency": profile.salary_currency,
        "query_hints": profile.query_hints,
        "confirmed_at": profile.confirmed_at,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _scan_payload(session: Session, scan: JobScan) -> dict:
    matches = list(
        session.scalars(
            select(JobScanMatch)
            .where(JobScanMatch.scan_id == scan.id)
            .order_by(JobScanMatch.rank)
        )
    )
    return {
        "id": str(scan.id),
        "profile_id": str(scan.profile_id),
        "status": scan.status,
        "query_plan": scan.query_plan_json,
        "providers": scan.provider_set_json,
        "scoring_version": scan.scoring_version,
        "top_k": scan.top_k,
        "jobs_seen": scan.jobs_seen,
        "jobs_after_filter": scan.jobs_after_filter,
        "jobs_ranked": scan.jobs_ranked,
        "started_at": scan.started_at,
        "completed_at": scan.completed_at,
        "error_code": scan.error_code,
        "error_detail": scan.error_detail,
        "matches": [
            {
                "id": str(item.id),
                "job_id": str(item.job_id),
                "provider": item.provider,
                "provider_job_id": item.provider_job_id,
                "application_url": item.application_url,
                "deterministic_score": item.deterministic_score,
                "score_breakdown": item.score_breakdown,
                "source_evidence": item.source_evidence,
                "rank": item.rank,
            }
            for item in matches
        ],
        "ai_reranking": "NOT_IMPLEMENTED",
        "scheduled_delivery": "NOT_IMPLEMENTED",
        "external_job_providers": "NOT_IMPLEMENTED",
        "realtime_streaming": "NOT_IMPLEMENTED",
        "autonomous_applications": "NOT_IMPLEMENTED",
    }


@router.get("/profile")
def get_profile(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    profile = session.scalar(select(JobSearchProfile).where(JobSearchProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job Radar profile not found")
    return _profile_payload(profile)


@router.put("/profile")
def put_profile(
    body: JobSearchProfileInput,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    if body.resume_version_id is not None:
        resume_version = session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == body.resume_version_id,
                ResumeVersion.user_id == user.id,
            )
        )
        if resume_version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume version not found")

    target_titles = _clean_values(body.target_titles, maximum_length=240)
    if not target_titles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one target title is required",
        )
    profile = session.scalar(select(JobSearchProfile).where(JobSearchProfile.user_id == user.id))
    if profile is None:
        profile = JobSearchProfile(user_id=user.id)
        session.add(profile)
    profile.resume_version_id = body.resume_version_id
    profile.target_titles = target_titles
    profile.skills = _clean_values(body.skills, maximum_length=160)
    profile.years_experience = body.years_experience
    profile.seniority_preferences = _clean_values(body.seniority_preferences, maximum_length=48)
    profile.preferred_locations = _clean_values(body.preferred_locations, maximum_length=240)
    profile.remote_policy = body.remote_policy
    profile.salary_min = body.salary_min
    profile.salary_currency = body.salary_currency.upper()
    profile.query_hints = profile.query_hints or {}
    profile.confirmed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(profile)
    return _profile_payload(profile)


@router.post("/scans")
def create_scan(
    body: JobScanRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    profile = session.scalar(select(JobSearchProfile).where(JobSearchProfile.user_id == user.id))
    if profile is None or profile.confirmed_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Confirm a Job Radar search profile before starting a scan",
        )
    if not supports_task_type(settings, "JOB_RADAR_SCAN"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job Radar scan execution is not configured for this environment",
        )

    request_key = (idempotency_key or str(uuid.uuid4())).strip()
    if not request_key or len(request_key) > 160:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key must be 1-160 characters",
        )
    existing = session.scalar(
        select(JobScan).where(
            JobScan.user_id == user.id,
            JobScan.idempotency_key == request_key,
        )
    )
    if existing is not None:
        return _scan_payload(session, existing)

    query_plan = build_query_plan(
        profile,
        max_queries=body.max_queries,
        per_query_limit=body.per_query_limit,
    )
    scan = JobScan(
        user_id=user.id,
        profile_id=profile.id,
        idempotency_key=request_key,
        status="QUEUED",
        query_plan_json=query_plan,
        provider_set_json=[PROVIDER_NAME],
        scoring_version=SCORING_VERSION,
        top_k=body.top_k,
    )
    session.add(scan)
    session.flush()
    add_task_outbox_event(
        session,
        task=Task(
            task_type="JOB_RADAR_SCAN",
            payload={"scan_id": str(scan.id)},
            idempotency_key=f"job-radar-scan:{scan.id}",
        ),
        aggregate_type="JobScan",
        aggregate_id=scan.id,
    )
    session.commit()

    if settings.task_queue_provider == "memory":
        run_job_scan(session, scan_id=scan.id)
        scan = session.get(JobScan, scan.id) or scan
    return _scan_payload(session, scan)


@router.get("/scans/{scan_id}")
def get_scan(
    scan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    scan = session.scalar(
        select(JobScan).where(JobScan.id == scan_id, JobScan.user_id == user.id)
    )
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job Radar scan not found")
    return _scan_payload(session, scan)
