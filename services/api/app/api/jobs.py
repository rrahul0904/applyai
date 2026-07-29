import uuid
import base64
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import (
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobRequirement,
    JobSkill,
    JobSource,
    JobSourceLink,
    SavedJob,
    User,
)
from app.schemas import JobDetail, JobSearchPage, JobSummary
from app.search.provider import JobSearchQuery, PostgresSearchProvider, SearchProvider


router = APIRouter(prefix="/jobs", tags=["jobs"])


def summary_for(
    job: Job,
    company: Company,
    location: JobLocation | None,
    compensation: JobCompensation | None,
    saved: bool,
) -> JobSummary:
    return JobSummary(
        id=job.id,
        title=job.title,
        company_name=company.canonical_name,
        location=location.location_text if location else None,
        work_mode=location.work_mode if location else None,
        minimum_compensation=compensation.minimum if compensation else None,
        maximum_compensation=compensation.maximum if compensation else None,
        compensation_provenance=compensation.provenance if compensation else None,
        posted_at=job.posted_at,
        last_seen_at=job.last_seen_at,
        saved=saved,
        data_origin=job.data_origin,
    )


def get_search_provider() -> SearchProvider:
    return PostgresSearchProvider()


def decode_cursor(value: str | None) -> tuple[datetime | None, uuid.UUID | None]:
    if not value:
        return None, None
    try:
        payload = json.loads(base64.urlsafe_b64decode(value.encode()).decode())
        return datetime.fromisoformat(payload["at"]), uuid.UUID(payload["id"])
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_CURSOR", "message": "Search cursor is invalid"},
        )


def encode_cursor(job: Job) -> str:
    sort_at = job.posted_at or job.first_seen_at
    payload = json.dumps({"at": sort_at.isoformat(), "id": str(job.id)}).encode()
    return base64.urlsafe_b64encode(payload).decode()


@router.get("", response_model=JobSearchPage)
def list_jobs(
    keyword: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=200),
    work_mode: str | None = Query(default=None, max_length=32),
    employment_type: str | None = Query(default=None, max_length=48),
    seniority: str | None = Query(default=None, max_length=48),
    company: str | None = Query(default=None, max_length=200),
    minimum_salary: int | None = Query(default=None, ge=0, le=10_000_000),
    posted_within_days: int | None = Query(default=None, ge=1, le=365),
    target_role: str | None = Query(default=None, max_length=200),
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    search: SearchProvider = Depends(get_search_provider),
) -> JobSearchPage:
    cursor_at, cursor_id = decode_cursor(cursor)
    jobs = list(
        session.scalars(
            search.jobs(
                JobSearchQuery(
                    keyword=keyword,
                    location=location,
                    work_mode=work_mode,
                    employment_type=employment_type,
                    seniority=seniority,
                    company=company,
                    minimum_salary=minimum_salary,
                    posted_within_days=posted_within_days,
                    target_role=target_role,
                    cursor_at=cursor_at,
                    cursor_id=cursor_id,
                )
            ).limit(limit + 1)
        ).unique()
    )
    has_more = len(jobs) > limit
    jobs = jobs[:limit]
    saved_ids = set(
        session.scalars(select(SavedJob.job_id).where(SavedJob.user_id == user.id))
    )
    results: list[JobSummary] = []
    for job in jobs:
        company_row = session.get(Company, job.company_id)
        if company_row is None:
            continue
        location_row = session.scalar(
            select(JobLocation).where(JobLocation.job_id == job.id).limit(1)
        )
        compensation = session.scalar(
            select(JobCompensation).where(JobCompensation.job_id == job.id).limit(1)
        )
        results.append(
            summary_for(job, company_row, location_row, compensation, job.id in saved_ids)
        )
    return JobSearchPage(
        items=results,
        next_cursor=encode_cursor(jobs[-1]) if has_more and jobs else None,
        returned=len(results),
    )


@router.get("/saved", response_model=list[JobSummary])
def list_saved_jobs(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[JobSummary]:
    saved_rows = list(
        session.scalars(
            select(SavedJob)
            .where(SavedJob.user_id == user.id)
            .order_by(SavedJob.created_at.desc())
        )
    )
    results: list[JobSummary] = []
    for saved in saved_rows:
        job = session.get(Job, saved.job_id)
        if job is None:
            continue
        company = session.get(Company, job.company_id)
        if company is None:
            continue
        location_row = session.scalar(
            select(JobLocation).where(JobLocation.job_id == job.id).limit(1)
        )
        compensation = session.scalar(
            select(JobCompensation).where(JobCompensation.job_id == job.id).limit(1)
        )
        results.append(summary_for(job, company, location_row, compensation, True))
    return results


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JobDetail:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    company = session.get(Company, job.company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    location_row = session.scalar(
        select(JobLocation).where(JobLocation.job_id == job.id).limit(1)
    )
    compensation = session.scalar(
        select(JobCompensation).where(JobCompensation.job_id == job.id).limit(1)
    )
    saved = (
        session.get(SavedJob, {"user_id": user.id, "job_id": job.id}) is not None
    )
    source_url = session.scalar(
        select(JobSource.source_url)
        .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
        .where(JobSourceLink.job_id == job.id)
        .order_by(JobSourceLink.is_primary.desc())
        .limit(1)
    )
    base = summary_for(job, company, location_row, compensation, saved)
    return JobDetail(
        **base.model_dump(),
        description=job.description,
        employment_type=job.employment_type,
        seniority=job.seniority,
        requirements=list(
            session.scalars(
                select(JobRequirement.text).where(JobRequirement.job_id == job.id)
            )
        ),
        skills=list(
            session.scalars(select(JobSkill.name).where(JobSkill.job_id == job.id))
        ),
        source_url=source_url,
        status=job.status,
    )


@router.post("/{job_id}/save", status_code=status.HTTP_204_NO_CONTENT)
def save_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    if session.get(Job, job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if session.get(SavedJob, {"user_id": user.id, "job_id": job_id}) is None:
        session.add(SavedJob(user_id=user.id, job_id=job_id))
        session.commit()


@router.delete("/{job_id}/save", status_code=status.HTTP_204_NO_CONTENT)
def unsave_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    saved = session.get(SavedJob, {"user_id": user.id, "job_id": job_id})
    if saved is not None:
        session.delete(saved)
        session.commit()
