from __future__ import annotations

import html
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.career_memory_models import CandidateCareerFact
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import Application, ApplicationEvent, Job, Notification, SavedJob, User
from app.platform_models import (
    ApplicationSubmissionRequest,
    CandidateAnalyticsEvent,
    CandidateContact,
    EmployerApplicant,
    EmployerJob,
    InterviewPracticeSession,
    NotificationPreference,
    ResumeStudioDocument,
    SavedSearch,
)

router = APIRouter(tags=["candidate platform"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SavedSearchWrite(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    query: dict[str, Any] = Field(default_factory=dict)
    alerts_enabled: bool = True
    minimum_match_score: int = Field(default=70, ge=0, le=100)


class SavedSearchResponse(SavedSearchWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class NotificationPreferenceWrite(BaseModel):
    email_enabled: bool = True
    push_enabled: bool = True
    job_match_enabled: bool = True
    application_reminder_enabled: bool = True
    interview_reminder_enabled: bool = True
    recruiter_followup_enabled: bool = True
    quiet_hours: dict[str, Any] = Field(default_factory=dict)


class NotificationPreferenceResponse(NotificationPreferenceWrite):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    updated_at: datetime


class NotificationResponse(BaseModel):
    id: uuid.UUID
    notification_type: str
    title: str
    body: str
    action_url: str | None
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class AnalyticsEventWrite(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    entity_type: str | None = Field(default=None, max_length=48)
    entity_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContactWrite(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    company: str | None = Field(default=None, max_length=240)
    title: str | None = Field(default=None, max_length=240)
    email: str | None = Field(default=None, max_length=320)
    linkedin_url: str | None = None
    relationship: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=8000)
    last_contacted_at: datetime | None = None
    followup_at: datetime | None = None


class ContactResponse(ContactWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ResumeDocumentWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    job_id: uuid.UUID | None = None
    base_resume_version_id: uuid.UUID | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    status: Literal["DRAFT", "REVIEWED", "FINAL"] = "DRAFT"


class ResumeDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    content: dict[str, Any] | None = None
    status: Literal["DRAFT", "REVIEWED", "FINAL"] | None = None


class ResumeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID | None
    base_resume_version_id: uuid.UUID | None
    title: str
    content: dict[str, Any]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class InterviewPracticeWrite(BaseModel):
    job_id: uuid.UUID
    mode: Literal["BEHAVIORAL", "TECHNICAL", "SYSTEM_DESIGN", "MANAGER", "MIXED"] = "BEHAVIORAL"
    responses: list[dict[str, Any]] = Field(default_factory=list)


class InterviewPracticeUpdate(BaseModel):
    responses: list[dict[str, Any]] | None = None
    feedback: dict[str, Any] | None = None
    score: int | None = Field(default=None, ge=0, le=100)


class InterviewPracticeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    mode: str
    responses: list[Any]
    feedback: dict[str, Any]
    score: int | None
    created_at: datetime
    updated_at: datetime


class SubmissionWrite(BaseModel):
    application_id: uuid.UUID
    mode: Literal["FIRST_PARTY", "EXTERNAL_HANDOFF"] = "EXTERNAL_HANDOFF"
    provider: str = Field(default="MANUAL", max_length=80)
    target_url: HttpUrl | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    application_id: uuid.UUID
    attempt_number: int
    mode: str
    provider: str
    status: str
    target_url: str | None
    payload: dict[str, Any]
    approved_at: datetime | None
    submitted_at: datetime | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


def _notification_response(item: Notification) -> NotificationResponse:
    payload = item.payload or {}
    return NotificationResponse(
        id=item.id,
        notification_type=item.notification_type,
        title=str(payload.get("title") or item.notification_type.replace("_", " ").title()),
        body=str(payload.get("body") or ""),
        action_url=payload.get("action_url"),
        payload=payload,
        read_at=item.read_at,
        created_at=item.created_at,
    )


def _owned_contact(session: Session, user: User, contact_id: uuid.UUID) -> CandidateContact:
    item = session.scalar(select(CandidateContact).where(CandidateContact.id == contact_id, CandidateContact.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return item


def _owned_resume_document(session: Session, user: User, document_id: uuid.UUID) -> ResumeStudioDocument:
    item = session.scalar(select(ResumeStudioDocument).where(ResumeStudioDocument.id == document_id, ResumeStudioDocument.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Resume document not found")
    return item


def _owned_submission(session: Session, user: User, submission_id: uuid.UUID) -> ApplicationSubmissionRequest:
    item = session.scalar(select(ApplicationSubmissionRequest).where(ApplicationSubmissionRequest.id == submission_id, ApplicationSubmissionRequest.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Submission request not found")
    return item


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
def list_saved_searches(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return list(session.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.updated_at.desc())))


@router.post("/saved-searches", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
def create_saved_search(payload: SavedSearchWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = SavedSearch(user_id=user.id, **payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/saved-searches/{search_id}", response_model=SavedSearchResponse)
def update_saved_search(search_id: uuid.UUID, payload: SavedSearchWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = session.scalar(select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    session.commit(); session.refresh(item)
    return item


@router.delete("/saved-searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(search_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> None:
    item = session.scalar(select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    session.delete(item); session.commit()


@router.get("/notification-preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = session.get(NotificationPreference, user.id)
    if item is None:
        item = NotificationPreference(user_id=user.id)
        session.add(item); session.commit(); session.refresh(item)
    return item


@router.put("/notification-preferences", response_model=NotificationPreferenceResponse)
def save_notification_preferences(payload: NotificationPreferenceWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = session.get(NotificationPreference, user.id)
    if item is None:
        item = NotificationPreference(user_id=user.id)
        session.add(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    session.commit(); session.refresh(item)
    return item


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(unread_only: bool = Query(default=False), limit: int = Query(default=50, ge=1, le=200), user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    items = list(session.scalars(query.order_by(Notification.created_at.desc()).limit(limit)))
    return [_notification_response(item) for item in items]


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def read_notification(notification_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = session.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    item.read_at = utcnow(); session.commit(); session.refresh(item)
    return _notification_response(item)


@router.post("/analytics/events", status_code=status.HTTP_204_NO_CONTENT)
def record_analytics_event(payload: AnalyticsEventWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> None:
    session.add(CandidateAnalyticsEvent(user_id=user.id, event_type=payload.event_type, entity_type=payload.entity_type, entity_id=payload.entity_id, metadata_json=payload.metadata))
    session.commit()


@router.get("/analytics/summary")
def analytics_summary(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    status_rows = session.execute(select(Application.current_status, func.count(Application.id)).where(Application.user_id == user.id).group_by(Application.current_status)).all()
    event_rows = session.execute(select(CandidateAnalyticsEvent.event_type, func.count(CandidateAnalyticsEvent.id)).where(CandidateAnalyticsEvent.user_id == user.id).group_by(CandidateAnalyticsEvent.event_type)).all()
    return {
        "applications": {key: int(value) for key, value in status_rows},
        "saved_jobs": int(session.scalar(select(func.count()).select_from(SavedJob).where(SavedJob.user_id == user.id)) or 0),
        "unread_notifications": int(session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))) or 0),
        "resume_documents": int(session.scalar(select(func.count()).select_from(ResumeStudioDocument).where(ResumeStudioDocument.user_id == user.id)) or 0),
        "interview_practice_sessions": int(session.scalar(select(func.count()).select_from(InterviewPracticeSession).where(InterviewPracticeSession.user_id == user.id)) or 0),
        "network_contacts": int(session.scalar(select(func.count()).select_from(CandidateContact).where(CandidateContact.user_id == user.id)) or 0),
        "events": {key: int(value) for key, value in event_rows},
    }


@router.get("/contacts", response_model=list[ContactResponse])
def list_contacts(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return list(session.scalars(select(CandidateContact).where(CandidateContact.user_id == user.id).order_by(CandidateContact.followup_at.asc().nullslast(), CandidateContact.updated_at.desc())))


@router.post("/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = CandidateContact(user_id=user.id, **payload.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return item


@router.put("/contacts/{contact_id}", response_model=ContactResponse)
def update_contact(contact_id: uuid.UUID, payload: ContactWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = _owned_contact(session, user, contact_id)
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    session.commit(); session.refresh(item)
    return item


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> None:
    item = _owned_contact(session, user, contact_id); session.delete(item); session.commit()


@router.get("/resume-studio", response_model=list[ResumeDocumentResponse])
def list_resume_documents(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return list(session.scalars(select(ResumeStudioDocument).where(ResumeStudioDocument.user_id == user.id).order_by(ResumeStudioDocument.updated_at.desc())))


@router.post("/resume-studio", response_model=ResumeDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_resume_document(payload: ResumeDocumentWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if payload.job_id and session.get(Job, payload.job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    item = ResumeStudioDocument(user_id=user.id, **payload.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return item


@router.post("/resume-studio/from-job/{job_id}", response_model=ResumeDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_resume_for_job(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    facts = list(session.scalars(select(CandidateCareerFact).where(CandidateCareerFact.user_id == user.id, CandidateCareerFact.archived_at.is_(None), CandidateCareerFact.user_verified.is_(True)).order_by(CandidateCareerFact.occurred_at.desc().nullslast()).limit(50)))
    item = ResumeStudioDocument(user_id=user.id, job_id=job.id, title=f"{job.title} resume", content={"target_role": job.title, "summary": "", "evidence": [{"id": str(fact.id), "category": fact.category, "title": fact.title, "text": fact.fact_text} for fact in facts], "sections": []})
    session.add(item); session.commit(); session.refresh(item)
    return item


@router.get("/resume-studio/{document_id}", response_model=ResumeDocumentResponse)
def get_resume_document(document_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return _owned_resume_document(session, user, document_id)


@router.put("/resume-studio/{document_id}", response_model=ResumeDocumentResponse)
def update_resume_document(document_id: uuid.UUID, payload: ResumeDocumentUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = _owned_resume_document(session, user, document_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items(): setattr(item, key, value)
    if "content" in changes: item.version += 1
    session.commit(); session.refresh(item)
    return item


def _flatten_resume(content: dict[str, Any]) -> str:
    lines: list[str] = []
    if content.get("summary"): lines.extend([str(content["summary"]), ""])
    for section in content.get("sections", []):
        if isinstance(section, dict):
            if section.get("heading"): lines.append(str(section["heading"]).upper())
            body = section.get("body")
            if isinstance(body, list): lines.extend(f"- {value}" for value in body)
            elif body: lines.append(str(body))
            lines.append("")
    if not lines and content.get("evidence"):
        lines.append("VERIFIED CAREER EVIDENCE")
        lines.extend(f"- {item.get('text', '')}" for item in content["evidence"] if isinstance(item, dict))
    return "\n".join(lines).strip()


@router.get("/resume-studio/{document_id}/export")
def export_resume_document(document_id: uuid.UUID, format: Literal["txt", "html"] = Query(default="txt"), user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = _owned_resume_document(session, user, document_id)
    text = _flatten_resume(item.content)
    if format == "html":
        content = "<!doctype html><html><body><pre>" + html.escape(text) + "</pre></body></html>"
        content_type = "text/html"
    else:
        content, content_type = text, "text/plain"
    return {"filename": f"{item.title.replace(' ', '-')}.{format}", "content_type": content_type, "content": content, "version": item.version}


@router.get("/interview-practice", response_model=list[InterviewPracticeResponse])
def list_interview_practice(job_id: uuid.UUID | None = None, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    query = select(InterviewPracticeSession).where(InterviewPracticeSession.user_id == user.id)
    if job_id: query = query.where(InterviewPracticeSession.job_id == job_id)
    return list(session.scalars(query.order_by(InterviewPracticeSession.updated_at.desc())))


@router.post("/interview-practice", response_model=InterviewPracticeResponse, status_code=status.HTTP_201_CREATED)
def create_interview_practice(payload: InterviewPracticeWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if session.get(Job, payload.job_id) is None: raise HTTPException(status_code=404, detail="Job not found")
    item = InterviewPracticeSession(user_id=user.id, **payload.model_dump())
    session.add(item); session.commit(); session.refresh(item)
    return item


@router.put("/interview-practice/{session_id}", response_model=InterviewPracticeResponse)
def update_interview_practice(session_id: uuid.UUID, payload: InterviewPracticeUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = session.scalar(select(InterviewPracticeSession).where(InterviewPracticeSession.id == session_id, InterviewPracticeSession.user_id == user.id))
    if item is None: raise HTTPException(status_code=404, detail="Interview practice session not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items(): setattr(item, key, value)
    if item.score is None and "responses" in changes:
        answers = [str(row.get("answer", "")) for row in item.responses if isinstance(row, dict)]
        item.score = min(100, round(sum(min(len(answer), 500) for answer in answers) / max(len(answers), 1) / 5)) if answers else 0
    session.commit(); session.refresh(item)
    return item


@router.get("/submissions", response_model=list[SubmissionResponse])
def list_submissions(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return list(session.scalars(select(ApplicationSubmissionRequest).where(ApplicationSubmissionRequest.user_id == user.id).order_by(ApplicationSubmissionRequest.created_at.desc())))


@router.post("/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_submission(payload: SubmissionWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    application = session.scalar(select(Application).where(Application.id == payload.application_id, Application.user_id == user.id))
    if application is None: raise HTTPException(status_code=404, detail="Application not found")
    attempt = int(session.scalar(select(func.count()).select_from(ApplicationSubmissionRequest).where(ApplicationSubmissionRequest.application_id == application.id)) or 0) + 1
    item = ApplicationSubmissionRequest(user_id=user.id, application_id=application.id, attempt_number=attempt, mode=payload.mode, provider=payload.provider, target_url=str(payload.target_url) if payload.target_url else None, payload=payload.payload)
    session.add(item); session.commit(); session.refresh(item)
    return item


@router.post("/submissions/{submission_id}/approve", response_model=SubmissionResponse)
def approve_submission(submission_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    item = _owned_submission(session, user, submission_id)
    if item.status not in {"DRAFT", "REVIEW_REQUIRED"}: raise HTTPException(status_code=409, detail="Submission cannot be approved from its current state")
    item.status = "APPROVED"; item.approved_at = utcnow(); session.commit(); session.refresh(item)
    return item


@router.post("/submissions/{submission_id}/execute")
def execute_submission(submission_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = _owned_submission(session, user, submission_id)
    if item.status != "APPROVED": raise HTTPException(status_code=409, detail="Candidate approval is required before submission")
    application = session.scalar(select(Application).where(Application.id == item.application_id, Application.user_id == user.id))
    if application is None: raise HTTPException(status_code=404, detail="Application not found")
    if item.mode == "FIRST_PARTY":
        employer_job = session.scalar(select(EmployerJob).where(EmployerJob.canonical_job_id == application.job_id, EmployerJob.status == "PUBLISHED"))
        if employer_job is None: raise HTTPException(status_code=409, detail="This role is not available for first-party submission")
        existing = session.scalar(select(EmployerApplicant).where(EmployerApplicant.employer_job_id == employer_job.id, EmployerApplicant.application_id == application.id))
        if existing is None: session.add(EmployerApplicant(employer_job_id=employer_job.id, application_id=application.id))
        previous = application.current_status
        application.current_status = "APPLIED"
        session.add(ApplicationEvent(application_id=application.id, actor_user_id=user.id, from_status=previous, to_status="APPLIED", metadata_json={"submission_request_id": str(item.id), "channel": "APPLYAI_FIRST_PARTY"}))
        item.status = "SUBMITTED"; item.submitted_at = utcnow(); session.commit()
        return {"status": item.status, "submitted": True, "channel": "FIRST_PARTY"}
    if not item.target_url: raise HTTPException(status_code=422, detail="External submission requires a target URL")
    item.status = "READY_FOR_CANDIDATE"; session.commit()
    return {"status": item.status, "submitted": False, "channel": "EXTERNAL_HANDOFF", "target_url": item.target_url, "message": "ApplyAI prepared the reviewed package; the candidate completes the external employer step."}
