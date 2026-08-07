from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.models import Application, EmployerOrganization, Interview, Job, Notification, User
from app.platform_models import (
    ApplicationSubmissionRequest,
    CandidateContact,
    EmployerApplicant,
    EmployerJob,
    ResumeStudioDocument,
    SavedSearch,
    Subscription,
)

router = APIRouter(prefix="/internal/platform", tags=["internal-platform"], dependencies=[Depends(require_internal_api)])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/metrics")
def platform_metrics(session: Session = Depends(get_session)) -> dict[str, Any]:
    def count(model) -> int:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)
    return {
        "users": count(User),
        "applications": count(Application),
        "employer_organizations": count(EmployerOrganization),
        "employer_jobs": count(EmployerJob),
        "employer_applicants": count(EmployerApplicant),
        "subscriptions": count(Subscription),
        "saved_searches": count(SavedSearch),
        "resume_studio_documents": count(ResumeStudioDocument),
        "submission_requests": count(ApplicationSubmissionRequest),
        "notifications": count(Notification),
    }


@router.get("/organizations")
def list_organizations(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    organizations = list(session.scalars(select(EmployerOrganization).order_by(EmployerOrganization.created_at.desc())))
    return [{"id": org.id, "name": org.name, "slug": org.slug, "verification_status": org.verification_status, "created_at": org.created_at} for org in organizations]


@router.post("/organizations/{organization_id}/verify")
def verify_organization(organization_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    org = session.get(EmployerOrganization, organization_id)
    if org is None: raise HTTPException(status_code=404, detail="Employer organization not found")
    org.verification_status = "VERIFIED"; session.commit()
    return {"id": org.id, "verification_status": org.verification_status}


@router.post("/organizations/{organization_id}/suspend")
def suspend_organization(organization_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    org = session.get(EmployerOrganization, organization_id)
    if org is None: raise HTTPException(status_code=404, detail="Employer organization not found")
    org.verification_status = "SUSPENDED"; session.commit()
    return {"id": org.id, "verification_status": org.verification_status}


def _notification_exists(session: Session, user_id: uuid.UUID, notification_type: str, key: str, value: str) -> bool:
    return session.scalar(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.notification_type == notification_type,
            Notification.payload[key].astext == value,
        ).limit(1)
    ) is not None


@router.post("/dispatch-engagement")
def dispatch_engagement(
    saved_search_job_limit: int = Query(default=3, ge=1, le=10),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    now = utcnow(); created = {"recruiter_followups": 0, "interviews": 0, "job_alerts": 0}

    due_contacts = list(session.scalars(select(CandidateContact).where(CandidateContact.followup_at.is_not(None), CandidateContact.followup_at <= now).limit(500)))
    for contact in due_contacts:
        key = str(contact.id)
        if _notification_exists(session, contact.user_id, "RECRUITER_FOLLOWUP", "contact_id", key): continue
        session.add(Notification(user_id=contact.user_id, notification_type="RECRUITER_FOLLOWUP", payload={"title": f"Follow up with {contact.name}", "body": f"Your planned networking follow-up with {contact.name} is due.", "action_url": "/network", "contact_id": key}))
        created["recruiter_followups"] += 1

    upcoming = list(session.execute(select(Interview, Application).join(Application, Application.id == Interview.application_id).where(Interview.scheduled_at.is_not(None), Interview.scheduled_at >= now, Interview.scheduled_at <= now + timedelta(hours=48)).limit(500)))
    for interview, application in upcoming:
        key = str(interview.id)
        if _notification_exists(session, interview.user_id, "INTERVIEW_REMINDER", "interview_id", key): continue
        session.add(Notification(user_id=interview.user_id, notification_type="INTERVIEW_REMINDER", payload={"title": "Interview coming up", "body": f"Your {interview.interview_type.lower()} interview is scheduled soon.", "action_url": f"/interview/{application.job_id}", "interview_id": key}))
        created["interviews"] += 1

    saved_searches = list(session.scalars(select(SavedSearch).where(SavedSearch.alerts_enabled.is_(True)).limit(500)))
    for saved in saved_searches:
        query = select(Job).where(Job.status == "ACTIVE")
        keyword = str((saved.query or {}).get("q") or "").strip()
        location = str((saved.query or {}).get("location") or "").strip()
        if keyword:
            pattern = f"%{keyword}%"; query = query.where(or_(Job.title.ilike(pattern), Job.description.ilike(pattern)))
        if location:
            query = query.where(Job.search_document.ilike(f"%{location}%"))
        jobs = list(session.scalars(query.order_by(Job.posted_at.desc().nullslast()).limit(saved_search_job_limit)))
        for job in jobs:
            alert_key = f"{saved.id}:{job.id}"
            if _notification_exists(session, saved.user_id, "JOB_ALERT", "alert_key", alert_key): continue
            session.add(Notification(user_id=saved.user_id, notification_type="JOB_ALERT", payload={"title": f"New match: {job.title}", "body": "A role matching one of your saved searches is available.", "action_url": f"/jobs/{job.id}", "saved_search_id": str(saved.id), "job_id": str(job.id), "alert_key": alert_key}))
            created["job_alerts"] += 1

    session.commit()
    return created
