from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import (
    candidate_context,
    get_or_create_application,
    get_owned_job,
)
from app.api.career_product import _application, _assistant_payload, _match_payload
from app.career_models import AIArtifact
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import ApplicationAnswer, Company, ResumeVersion, User

router = APIRouter(prefix="/career-system", tags=["career system"])

RECRUITER_MESSAGE_KEY = "APPLYAI_CAREER_SYSTEM:RECRUITER_MESSAGE"
FOLLOW_UP_MESSAGE_KEY = "APPLYAI_CAREER_SYSTEM:FOLLOW_UP_MESSAGE"


class CareerSystemCommunicationWrite(BaseModel):
    recruiter_message: str = Field(min_length=1, max_length=5000)
    recruiter_message_verified: bool = False
    follow_up_message: str = Field(min_length=1, max_length=5000)
    follow_up_message_verified: bool = False


def _saved_answer(
    session: Session,
    *,
    application_id: uuid.UUID | None,
    key: str,
) -> ApplicationAnswer | None:
    if application_id is None:
        return None
    return session.scalar(
        select(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application_id,
            ApplicationAnswer.question == key,
        )
    )


def _latest_resume(session: Session, user: User) -> ResumeVersion | None:
    return session.scalar(
        select(ResumeVersion)
        .where(ResumeVersion.user_id == user.id)
        .order_by(ResumeVersion.created_at.desc())
        .limit(1)
    )


def _latest_interview_artifact(
    session: Session,
    *,
    user: User,
    job_id: uuid.UUID,
) -> AIArtifact | None:
    return session.scalar(
        select(AIArtifact)
        .where(
            AIArtifact.user_id == user.id,
            AIArtifact.job_id == job_id,
            AIArtifact.artifact_type == "INTERVIEW_PREP",
            AIArtifact.superseded_at.is_(None),
        )
        .order_by(AIArtifact.version.desc(), AIArtifact.created_at.desc())
        .limit(1)
    )


def _portfolio_preview(session: Session, user: User, job_title: str) -> dict:
    candidate = candidate_context(session, user)
    profile = candidate["profile"]
    experiences = candidate["experiences"]
    skills = candidate["skills"]

    headline = None
    about = None
    if profile is not None:
        headline = profile.headline or profile.current_title
        about = profile.summary

    highlights = []
    for experience in experiences[:4]:
        highlights.append(
            {
                "title": experience.title,
                "company": experience.company_name,
                "description": experience.description,
                "provenance": experience.provenance,
            }
        )

    return {
        "headline": headline or "Professional profile",
        "about": about
        or "Add a verified professional summary to build your portfolio introduction.",
        "target_context": job_title,
        "highlights": highlights,
        "skills": [item.name for item in skills[:16]],
        "safety": {
            "policy": "VERIFIED_EVIDENCE_ONLY",
            "message": (
                "This preview contains only saved candidate/profile evidence and does not "
                "invent accomplishments."
            ),
        },
    }


def _communication_drafts(
    session: Session,
    *,
    user: User,
    job,
    match: dict,
    application_id: uuid.UUID | None,
) -> dict:
    company = session.get(Company, job.company_id)
    company_name = company.canonical_name if company else "the company"
    candidate = candidate_context(session, user)
    profile = candidate["profile"]
    matched = match.get("matched_skills") or []
    skill_phrase = ", ".join(matched[:3])
    role_phrase = (
        profile.current_title
        if profile and profile.current_title
        else "my current professional background"
    )

    recruiter_default = (
        f"Hi — I’m interested in the {job.title} role at {company_name}. "
        f"My verified background as {role_phrase}"
        + (f" includes experience with {skill_phrase}." if skill_phrase else ".")
        + " I’d welcome the chance to learn more about the team’s priorities and whether "
        "my background could be relevant."
    )
    follow_up_default = (
        f"Hi — I wanted to follow up on my application for the {job.title} role at "
        f"{company_name}. I remain interested in the opportunity and would be glad to "
        "provide any additional context about my experience. Thank you for your time and "
        "consideration."
    )

    recruiter_saved = _saved_answer(
        session,
        application_id=application_id,
        key=RECRUITER_MESSAGE_KEY,
    )
    follow_up_saved = _saved_answer(
        session,
        application_id=application_id,
        key=FOLLOW_UP_MESSAGE_KEY,
    )
    return {
        "recruiter_message": recruiter_saved.answer if recruiter_saved else recruiter_default,
        "recruiter_message_verified": bool(recruiter_saved and recruiter_saved.user_verified),
        "follow_up_message": follow_up_saved.answer if follow_up_saved else follow_up_default,
        "follow_up_message_verified": bool(follow_up_saved and follow_up_saved.user_verified),
        "policy": "CANDIDATE_REVIEW_REQUIRED",
    }


def _fallback_interview_questions(job, match: dict) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    for skill in (match.get("matched_skills") or [])[:2]:
        questions.append(
            {
                "focus": skill,
                "question": (
                    f"Walk me through a concrete example where you used {skill}. "
                    "What did you own, what trade-offs did you make, and what was the outcome?"
                ),
            }
        )
    for skill in (match.get("missing_skills") or [])[:2]:
        questions.append(
            {
                "focus": skill,
                "question": (
                    f"The role emphasizes {skill}, which is not explicit in your verified "
                    "profile. What adjacent experience would help you ramp up without "
                    "overstating your background?"
                ),
            }
        )
    questions.append(
        {
            "focus": "role motivation",
            "question": f"Why is the {job.title} role the right next step for you now?",
        }
    )
    questions.append(
        {
            "focus": "ownership",
            "question": (
                "Tell me about a high-impact problem you owned when requirements were ambiguous. "
                "How did you decide what to do and measure the result?"
            ),
        }
    )
    return questions[:6]


def _career_system_payload(session: Session, user: User, job) -> dict:
    match = _match_payload(session, user, job)
    assistant = _assistant_payload(session, user, job)
    application = _application(session, user, job.id)
    resume = _latest_resume(session, user)
    interview = _latest_interview_artifact(session, user=user, job_id=job.id)
    candidate = candidate_context(session, user)

    communications = _communication_drafts(
        session,
        user=user,
        job=job,
        match=match,
        application_id=application.id if application else None,
    )
    portfolio = _portfolio_preview(session, user, job.title)

    profile_ready = bool(
        candidate["profile"] and candidate["skills"] and candidate["experiences"]
    )
    resume_ready = bool(
        resume
        and resume.upload_status == "UPLOADED"
        and resume.processing_status in {"NEEDS_REVIEW", "COMPLETED"}
    )
    fit_ready = True
    package_ready = assistant["readiness_score"] == 100
    outreach_ready = bool(
        communications["recruiter_message_verified"]
        and communications["follow_up_message_verified"]
    )
    interview_ready = interview is not None
    application_started = application is not None

    stages = [
        {
            "id": "profile",
            "label": "Verified career profile",
            "complete": profile_ready,
            "weight": 15,
        },
        {
            "id": "resume",
            "label": "Processed master resume",
            "complete": resume_ready,
            "weight": 15,
        },
        {
            "id": "fit",
            "label": "Role fit analyzed",
            "complete": fit_ready,
            "weight": 15,
        },
        {
            "id": "package",
            "label": "Application package reviewed",
            "complete": package_ready,
            "weight": 25,
        },
        {
            "id": "outreach",
            "label": "Outreach and follow-up reviewed",
            "complete": outreach_ready,
            "weight": 10,
        },
        {
            "id": "interview",
            "label": "Interview preparation created",
            "complete": interview_ready,
            "weight": 10,
        },
        {
            "id": "application",
            "label": "Application workspace started",
            "complete": application_started,
            "weight": 10,
        },
    ]
    progress_score = sum(stage["weight"] for stage in stages if stage["complete"])
    next_stage = next((stage for stage in stages if not stage["complete"]), None)

    return {
        "job_id": job.id,
        "job_title": job.title,
        "company_name": assistant["company_name"],
        "application_id": application.id if application else None,
        "application_status": application.current_status if application else None,
        "progress_score": progress_score,
        "progress_explanation": (
            "Career System progress measures completion of your preparation workflow. "
            "It is not a hiring probability or employer prediction."
        ),
        "next_action": next_stage,
        "stages": stages,
        "resume": {
            "version_id": resume.id if resume else None,
            "filename": resume.filename if resume else None,
            "upload_status": resume.upload_status if resume else None,
            "processing_status": resume.processing_status if resume else None,
            "ready": resume_ready,
        },
        "match": match,
        "application_package": {
            "readiness_score": assistant["readiness_score"],
            "ready_to_finalize": assistant["ready_to_finalize"],
            "cover_letter_verified": assistant["cover_letter_verified"],
            "question_count": len(assistant["questions"]),
            "verified_question_count": sum(
                1 for item in assistant["questions"] if item["user_verified"]
            ),
            "checklist": assistant["checklist"],
        },
        "communications": communications,
        "portfolio_preview": portfolio,
        "interview": {
            "ready": interview_ready,
            "artifact_id": interview.id if interview else None,
            "status": interview.status if interview else "NOT_STARTED",
            "candidate_verified": bool(interview and interview.candidate_verified),
            "content": interview.content_json if interview else None,
            "starter_questions": []
            if interview
            else _fallback_interview_questions(job, match),
        },
        "actions": {
            "resume": "/resume/studio",
            "career_memory": "/career",
            "application": f"/applications/{application.id}" if application else None,
            "interview_task": "interview-prep",
        },
        "safety": {
            "evidence_policy": "VERIFIED_EVIDENCE_ONLY",
            "external_action_policy": "CANDIDATE_REVIEW_REQUIRED",
        },
    }


@router.get("/jobs/{job_id}")
def get_career_system(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return _career_system_payload(session, user, get_owned_job(job_id, session))


@router.put("/jobs/{job_id}/communications")
def save_career_system_communications(
    job_id: uuid.UUID,
    payload: CareerSystemCommunicationWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)

    values: list[tuple[str, str, bool]] = [
        (
            RECRUITER_MESSAGE_KEY,
            payload.recruiter_message.strip(),
            payload.recruiter_message_verified,
        ),
        (
            FOLLOW_UP_MESSAGE_KEY,
            payload.follow_up_message.strip(),
            payload.follow_up_message_verified,
        ),
    ]
    for key, answer, verified in values:
        row = session.scalar(
            select(ApplicationAnswer).where(
                ApplicationAnswer.application_id == application.id,
                ApplicationAnswer.question == key,
            )
        )
        if row is None:
            session.add(
                ApplicationAnswer(
                    application_id=application.id,
                    user_id=user.id,
                    question=key,
                    answer=answer,
                    user_verified=verified,
                )
            )
        else:
            if row.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application asset not found",
                )
            row.answer = answer
            row.user_verified = verified
    session.commit()
    return _career_system_payload(session, user, job)
