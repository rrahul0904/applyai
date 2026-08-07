from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import (
    Application,
    Company,
    EmployerOrganization,
    Job,
    JobCompensation,
    JobLocation,
    JobStatusHistory,
    JobVersion,
    OrganizationMember,
    User,
)
from app.platform_models import EmployerApplicant, EmployerJob

router = APIRouter(prefix="/employer", tags=["employer platform"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())


def slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "company"
    return base[:150]


class OrganizationWrite(BaseModel):
    name: str = Field(min_length=2, max_length=240)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    verification_status: str
    created_at: datetime


class MemberWrite(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["ADMIN", "RECRUITER", "HIRING_MANAGER"] = "RECRUITER"


class EmployerJobWrite(BaseModel):
    title: str = Field(min_length=2, max_length=280)
    description: str = Field(min_length=20, max_length=100000)
    location_text: str | None = Field(default=None, max_length=280)
    work_mode: Literal["REMOTE", "HYBRID", "ONSITE"] = "ONSITE"
    employment_type: str | None = Field(default=None, max_length=48)
    seniority: str | None = Field(default=None, max_length=48)
    compensation_min: int | None = Field(default=None, ge=0)
    compensation_max: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class EmployerJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    canonical_job_id: uuid.UUID | None
    title: str
    description: str
    location_text: str | None
    work_mode: str
    employment_type: str | None
    seniority: str | None
    compensation_min: int | None
    compensation_max: int | None
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime


class ApplicantUpdate(BaseModel):
    stage: Literal["NEW", "SCREEN", "INTERVIEW", "FINAL", "OFFER", "HIRED", "REJECTED"] | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    note: str | None = Field(default=None, max_length=8000)


class ApplicantResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    candidate_user_id: uuid.UUID
    candidate_email: str
    stage: str
    rating: int | None
    notes: list[Any]
    application_status: str
    created_at: datetime
    updated_at: datetime


def _membership(session: Session, user: User, organization_id: uuid.UUID) -> OrganizationMember:
    member = session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id))
    if member is None:
        raise HTTPException(status_code=403, detail="Employer organization access required")
    return member


def _admin_membership(session: Session, user: User, organization_id: uuid.UUID) -> OrganizationMember:
    member = _membership(session, user, organization_id)
    if member.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Employer administrator access required")
    return member


def _owned_job(session: Session, user: User, job_id: uuid.UUID) -> EmployerJob:
    item = session.get(EmployerJob, job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Employer job not found")
    _membership(session, user, item.organization_id)
    return item


@router.get("/organizations", response_model=list[OrganizationResponse])
def list_organizations(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return list(session.scalars(select(EmployerOrganization).join(OrganizationMember, OrganizationMember.organization_id == EmployerOrganization.id).where(OrganizationMember.user_id == user.id).order_by(EmployerOrganization.name)))


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    base = slugify(payload.name)
    slug = base
    counter = 1
    while session.scalar(select(EmployerOrganization.id).where(EmployerOrganization.slug == slug)) is not None:
        counter += 1
        slug = f"{base[:140]}-{counter}"
    org = EmployerOrganization(name=payload.name.strip(), slug=slug, verification_status="UNVERIFIED")
    session.add(org); session.flush()
    session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="ADMIN"))
    session.commit(); session.refresh(org)
    return org


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
def get_organization(organization_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _membership(session, user, organization_id)
    org = session.get(EmployerOrganization, organization_id)
    if org is None: raise HTTPException(status_code=404, detail="Employer organization not found")
    return org


@router.post("/organizations/{organization_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(organization_id: uuid.UUID, payload: MemberWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _admin_membership(session, user, organization_id)
    target = session.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if target is None: raise HTTPException(status_code=404, detail="User with that email does not exist")
    existing = session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == target.id))
    if existing:
        existing.role = payload.role
    else:
        session.add(OrganizationMember(organization_id=organization_id, user_id=target.id, role=payload.role))
    session.commit()
    return {"organization_id": organization_id, "user_id": target.id, "role": payload.role}


@router.get("/organizations/{organization_id}/jobs", response_model=list[EmployerJobResponse])
def list_employer_jobs(organization_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _membership(session, user, organization_id)
    return list(session.scalars(select(EmployerJob).where(EmployerJob.organization_id == organization_id).order_by(EmployerJob.updated_at.desc())))


@router.post("/organizations/{organization_id}/jobs", response_model=EmployerJobResponse, status_code=status.HTTP_201_CREATED)
def create_employer_job(organization_id: uuid.UUID, payload: EmployerJobWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _membership(session, user, organization_id)
    if payload.compensation_min is not None and payload.compensation_max is not None and payload.compensation_max < payload.compensation_min:
        raise HTTPException(status_code=422, detail="Maximum compensation must be at least minimum compensation")
    item = EmployerJob(organization_id=organization_id, created_by_user_id=user.id, **payload.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return item


@router.put("/jobs/{job_id}", response_model=EmployerJobResponse)
def update_employer_job(job_id: uuid.UUID, payload: EmployerJobWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = _owned_job(session, user, job_id)
    if item.status == "CLOSED": raise HTTPException(status_code=409, detail="Closed jobs cannot be edited")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    session.commit(); session.refresh(item)
    return item


@router.post("/jobs/{job_id}/publish", response_model=EmployerJobResponse)
def publish_employer_job(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = _owned_job(session, user, job_id)
    org = session.get(EmployerOrganization, item.organization_id)
    if org is None: raise HTTPException(status_code=404, detail="Employer organization not found")
    if org.verification_status != "VERIFIED": raise HTTPException(status_code=409, detail="Organization must be verified before publishing jobs")
    if item.canonical_job_id is None:
        normalized_company = normalize(org.name)
        company = session.scalar(select(Company).where(Company.normalized_name == normalized_company))
        if company is None:
            company = Company(canonical_name=org.name, normalized_name=normalized_company)
            session.add(company); session.flush()
        canonical = Job(company_id=company.id, title=item.title, normalized_title=normalize(item.title), description=item.description, search_document=f"{item.title} {org.name} {item.description} {item.location_text or ''}", employment_type=item.employment_type, seniority=item.seniority, status="ACTIVE", posted_at=utcnow(), last_seen_at=utcnow(), data_origin="FIRST_PARTY_EMPLOYER")
        session.add(canonical); session.flush()
        if item.location_text:
            session.add(JobLocation(job_id=canonical.id, location_text=item.location_text, work_mode=item.work_mode))
        if item.compensation_min is not None or item.compensation_max is not None:
            session.add(JobCompensation(job_id=canonical.id, minimum=item.compensation_min, maximum=item.compensation_max, currency=item.currency, interval="YEAR", provenance="EMPLOYER_VERIFIED"))
        session.add(JobVersion(job_id=canonical.id, version_number=1, snapshot={"title": item.title, "description": item.description, "location_text": item.location_text, "work_mode": item.work_mode, "employment_type": item.employment_type, "seniority": item.seniority, "compensation_min": item.compensation_min, "compensation_max": item.compensation_max, "currency": item.currency, "source": "EMPLOYER"}))
        session.add(JobStatusHistory(job_id=canonical.id, from_status=None, to_status="ACTIVE", reason="EMPLOYER_PUBLISHED"))
        item.canonical_job_id = canonical.id
    else:
        canonical = session.get(Job, item.canonical_job_id)
        if canonical:
            canonical.title = item.title; canonical.normalized_title = normalize(item.title); canonical.description = item.description; canonical.search_document = f"{item.title} {org.name} {item.description} {item.location_text or ''}"; canonical.employment_type = item.employment_type; canonical.seniority = item.seniority; canonical.status = "ACTIVE"; canonical.last_seen_at = utcnow(); canonical.closed_at = None
    item.status = "PUBLISHED"
    session.commit(); session.refresh(item)
    return item


@router.post("/jobs/{job_id}/close", response_model=EmployerJobResponse)
def close_employer_job(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = _owned_job(session, user, job_id)
    item.status = "CLOSED"
    if item.canonical_job_id:
        canonical = session.get(Job, item.canonical_job_id)
        if canonical and canonical.status != "CLOSED":
            previous = canonical.status; canonical.status = "CLOSED"; canonical.closed_at = utcnow(); session.add(JobStatusHistory(job_id=canonical.id, from_status=previous, to_status="CLOSED", reason="EMPLOYER_CLOSED"))
    session.commit(); session.refresh(item)
    return item


@router.get("/jobs/{job_id}/applicants", response_model=list[ApplicantResponse])
def list_applicants(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    employer_job = _owned_job(session, user, job_id)
    rows = session.execute(select(EmployerApplicant, Application, User).join(Application, Application.id == EmployerApplicant.application_id).join(User, User.id == Application.user_id).where(EmployerApplicant.employer_job_id == employer_job.id).order_by(EmployerApplicant.updated_at.desc())).all()
    return [ApplicantResponse(id=applicant.id, application_id=application.id, candidate_user_id=candidate.id, candidate_email=candidate.email, stage=applicant.stage, rating=applicant.rating, notes=applicant.notes, application_status=application.current_status, created_at=applicant.created_at, updated_at=applicant.updated_at) for applicant, application, candidate in rows]


@router.patch("/applicants/{applicant_id}", response_model=ApplicantResponse)
def update_applicant(applicant_id: uuid.UUID, payload: ApplicantUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    applicant = session.get(EmployerApplicant, applicant_id)
    if applicant is None: raise HTTPException(status_code=404, detail="Applicant not found")
    employer_job = _owned_job(session, user, applicant.employer_job_id)
    application = session.get(Application, applicant.application_id)
    if application is None: raise HTTPException(status_code=404, detail="Application not found")
    candidate = session.get(User, application.user_id)
    if candidate is None: raise HTTPException(status_code=404, detail="Candidate not found")
    if payload.stage is not None: applicant.stage = payload.stage
    if payload.rating is not None: applicant.rating = payload.rating
    if payload.note:
        applicant.notes = [*applicant.notes, {"body": payload.note, "at": utcnow().isoformat(), "actor_user_id": str(user.id)}]
    session.commit(); session.refresh(applicant)
    return ApplicantResponse(id=applicant.id, application_id=application.id, candidate_user_id=candidate.id, candidate_email=candidate.email, stage=applicant.stage, rating=applicant.rating, notes=applicant.notes, application_status=application.current_status, created_at=applicant.created_at, updated_at=applicant.updated_at)


@router.get("/organizations/{organization_id}/dashboard")
def employer_dashboard(organization_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    _membership(session, user, organization_id)
    job_ids = list(session.scalars(select(EmployerJob.id).where(EmployerJob.organization_id == organization_id)))
    status_rows = session.execute(select(EmployerJob.status, func.count(EmployerJob.id)).where(EmployerJob.organization_id == organization_id).group_by(EmployerJob.status)).all()
    applicants = int(session.scalar(select(func.count()).select_from(EmployerApplicant).where(EmployerApplicant.employer_job_id.in_(job_ids))) or 0) if job_ids else 0
    stage_rows = session.execute(select(EmployerApplicant.stage, func.count(EmployerApplicant.id)).where(EmployerApplicant.employer_job_id.in_(job_ids)).group_by(EmployerApplicant.stage)).all() if job_ids else []
    return {"jobs": {key: int(value) for key, value in status_rows}, "applicant_count": applicants, "applicants_by_stage": {key: int(value) for key, value in stage_rows}}
