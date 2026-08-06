from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import (
    TailoringWrite,
    candidate_context,
    get_or_create_application,
    get_owned_job,
    save_tailoring,
    tailoring_payload,
)
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import (
    Application,
    ApplicationAnswer,
    ApplicationEvent,
    CandidateExperience,
    CandidateProfile,
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobRequirement,
    JobSkill,
    JobSource,
    JobSourceLink,
    User,
)

router = APIRouter(prefix="/career-v1", tags=["career intelligence v1"])

ENGINE_VERSION = "applyai-explainable-fit-v1"
FINAL_RESUME_KEY = "APPLYAI_CAREER_V1:FINAL_RESUME"
COVER_LETTER_KEY = "APPLYAI_CAREER_V1:COVER_LETTER"
QUESTION_PREFIX = "APPLYAI_CAREER_V1:QUESTION:"
PACKAGE_KEY = "APPLYAI_CAREER_V1:PACKAGE"


class AssistantAnswerWrite(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)
    user_verified: bool = False


class AssistantWrite(BaseModel):
    cover_letter: str = Field(min_length=1, max_length=12000)
    cover_letter_verified: bool = False
    answers: list[AssistantAnswerWrite] = Field(default_factory=list, max_length=12)


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", value.lower())
        if len(token) > 2
    }


def _application(
    session: Session, user: User, job_id: uuid.UUID
) -> Application | None:
    return session.scalar(
        select(Application).where(
            Application.user_id == user.id,
            Application.job_id == job_id,
        )
    )


def _job_context(session: Session, job: Job) -> dict:
    company = session.get(Company, job.company_id)
    location = session.scalar(
        select(JobLocation)
        .where(JobLocation.job_id == job.id)
        .order_by(JobLocation.id)
        .limit(1)
    )
    compensation = session.scalar(
        select(JobCompensation)
        .where(JobCompensation.job_id == job.id)
        .order_by(JobCompensation.id)
        .limit(1)
    )
    skills = list(
        session.scalars(
            select(JobSkill)
            .where(JobSkill.job_id == job.id)
            .order_by(JobSkill.required.desc(), JobSkill.name)
        )
    )
    requirements = list(
        session.scalars(
            select(JobRequirement)
            .where(JobRequirement.job_id == job.id)
            .order_by(JobRequirement.required.desc(), JobRequirement.id)
        )
    )
    source_url = session.scalar(
        select(JobSource.source_url)
        .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
        .where(JobSourceLink.job_id == job.id)
        .order_by(JobSourceLink.is_primary.desc())
        .limit(1)
    )
    return {
        "company": company,
        "location": location,
        "compensation": compensation,
        "skills": skills,
        "requirements": requirements,
        "source_url": source_url,
    }


def _factor_breakdown(session: Session, user: User, job: Job) -> dict:
    candidate = candidate_context(session, user)
    profile: CandidateProfile | None = candidate["profile"]
    preference = candidate["preference"]
    context = _job_context(session, job)
    job_skills: list[JobSkill] = context["skills"]

    role_overlap = sorted(candidate["role_tokens"] & _tokens(job.title))
    role_score = min(30, 10 + len(role_overlap) * 5) if role_overlap else 5

    candidate_skills = {item.normalized_name for item in candidate["skills"]}
    matched_skills = [
        skill.name for skill in job_skills if skill.normalized_name in candidate_skills
    ]
    missing_skills = [
        skill.name
        for skill in job_skills
        if skill.required and skill.normalized_name not in candidate_skills
    ]
    required_count = max(1, sum(1 for item in job_skills if item.required))
    matched_required = sum(
        1
        for item in job_skills
        if item.required and item.normalized_name in candidate_skills
    )
    skill_score = round(30 * matched_required / required_count) if job_skills else 15

    location: JobLocation | None = context["location"]
    preferred_modes = {
        mode.upper() for mode in (preference.work_modes if preference else [])
    }
    preferred_location = (
        preference.location_text.lower()
        if preference and preference.location_text
        else None
    )
    location_score = 7
    location_reason = "Location fit is neutral because no preference was supplied."
    if location:
        if preferred_location and preferred_location in location.location_text.lower():
            location_score = 15
            location_reason = "The location matches the saved candidate preference."
        elif location.work_mode.upper() in preferred_modes:
            location_score = 13
            location_reason = "The work arrangement matches the saved preference."
        elif preferred_location or preferred_modes:
            location_score = 2
            location_reason = "The location or work arrangement is outside the first preference."

    compensation: JobCompensation | None = context["compensation"]
    target = preference.minimum_compensation if preference else None
    compensation_score = 7
    compensation_reason = "The posting does not provide enough compensation evidence."
    if target is None:
        compensation_score = 10
        compensation_reason = "No minimum compensation target is saved."
    elif compensation and compensation.maximum is not None:
        if compensation.maximum >= target:
            compensation_score = 15
            compensation_reason = "The published range can meet the saved compensation target."
        else:
            compensation_score = 0
            compensation_reason = "The published range is below the saved compensation target."

    seniority_score = 3
    seniority_reason = "Seniority fit should be confirmed with the recruiter."
    years = profile.years_experience if profile else None
    if years is not None and (job.seniority or "").upper() in {
        "SENIOR",
        "LEAD",
        "MANAGER",
        "DIRECTOR",
    }:
        seniority_score = 5 if years >= 7 else 2
        seniority_reason = (
            "Verified years of experience support the role seniority."
            if years >= 7
            else "The role may require more senior experience than the profile shows."
        )

    last_seen = job.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    age_days = max(0, (datetime.now(timezone.utc) - last_seen).days)
    freshness_score = 5 if age_days <= 7 else 3 if age_days <= 30 else 1
    freshness_reason = (
        "The role was verified during the last week."
        if age_days <= 7
        else f"The role was last verified {age_days} days ago."
    )

    total = min(
        100,
        role_score
        + skill_score
        + location_score
        + compensation_score
        + seniority_score
        + freshness_score,
    )
    if total >= 80:
        decision, band = "PRIORITIZE", "STRONG"
    elif total >= 65:
        decision, band = "CONSIDER", "GOOD"
    elif total >= 50:
        decision, band = "STRETCH", "PARTIAL"
    else:
        decision, band = "SKIP", "WEAK"

    candidate_text = " ".join(
        [
            profile.summary if profile and profile.summary else "",
            " ".join(item.description or "" for item in candidate["experiences"]),
            " ".join(item.name for item in candidate["skills"]),
        ]
    )
    candidate_tokens = _tokens(candidate_text)
    missing_requirements = [
        item.text
        for item in context["requirements"]
        if item.required
        and _tokens(item.text)
        and not (_tokens(item.text) & candidate_tokens)
    ][:5]

    signal_count = (
        int(profile is not None)
        + int(bool(candidate["roles"]))
        + int(bool(candidate["skills"]))
        + int(bool(job_skills))
        + int(location is not None)
        + int(compensation is not None)
    )
    confidence = "HIGH" if signal_count >= 6 else "MEDIUM" if signal_count >= 4 else "LOW"

    breakdown = [
        {
            "factor": "ROLE_ALIGNMENT",
            "score": role_score,
            "maximum": 30,
            "reason": (
                f"Matched role concepts: {', '.join(role_overlap)}."
                if role_overlap
                else "No direct target-role title overlap was found."
            ),
        },
        {
            "factor": "VERIFIED_SKILLS",
            "score": skill_score,
            "maximum": 30,
            "reason": (
                f"Matched verified skills: {', '.join(matched_skills)}."
                if matched_skills
                else "No required skill was explicitly matched."
            ),
        },
        {
            "factor": "LOCATION_AND_WORK_MODE",
            "score": location_score,
            "maximum": 15,
            "reason": location_reason,
        },
        {
            "factor": "COMPENSATION",
            "score": compensation_score,
            "maximum": 15,
            "reason": compensation_reason,
        },
        {
            "factor": "SENIORITY",
            "score": seniority_score,
            "maximum": 5,
            "reason": seniority_reason,
        },
        {
            "factor": "FRESHNESS",
            "score": freshness_score,
            "maximum": 5,
            "reason": freshness_reason,
        },
    ]
    strengths = [
        row["reason"]
        for row in breakdown
        if row["score"] >= max(1, round(row["maximum"] * 0.75))
    ]
    risks = []
    if missing_skills:
        risks.append(f"Missing required skills: {', '.join(missing_skills[:5])}.")
    if missing_requirements:
        risks.append(
            "The profile does not explicitly support: "
            + "; ".join(missing_requirements[:3])
        )
    if location_score <= 2:
        risks.append(location_reason)
    if compensation_score == 0:
        risks.append(compensation_reason)
    if not risks:
        risks.append("Confirm team scope, reporting line, and first-year expectations.")

    return {
        "match_score": total,
        "fit_band": band,
        "decision": decision,
        "confidence": confidence,
        "engine_version": ENGINE_VERSION,
        "breakdown": breakdown,
        "strengths": strengths[:5],
        "risks": risks[:5],
        "matched_skills": matched_skills[:10],
        "missing_skills": missing_skills[:10],
        "missing_requirements": missing_requirements,
        "source_url": context["source_url"],
    }


def _match_payload(session: Session, user: User, job: Job) -> dict:
    context = _job_context(session, job)
    factors = _factor_breakdown(session, user, job)
    company: Company | None = context["company"]
    location: JobLocation | None = context["location"]
    compensation: JobCompensation | None = context["compensation"]
    return {
        "job_id": job.id,
        "title": job.title,
        "company_name": company.canonical_name if company else "Unknown company",
        "location": location.location_text if location else None,
        "work_mode": location.work_mode if location else None,
        "minimum_compensation": compensation.minimum if compensation else None,
        "maximum_compensation": compensation.maximum if compensation else None,
        "posted_at": job.posted_at,
        "last_seen_at": job.last_seen_at,
        "description": job.description,
        **factors,
        "summary": (
            f"{factors['decision'].title()}: {factors['match_score']}% fit with "
            f"{factors['confidence'].lower()} confidence. This ranks opportunities; "
            "it does not predict an employer decision."
        ),
    }


@router.get("/matches")
def list_matches(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    jobs = list(
        session.scalars(
            select(Job)
            .where(Job.status == "ACTIVE")
            .order_by(Job.posted_at.desc().nullslast(), Job.last_seen_at.desc())
            .limit(250)
        )
    )
    items = [_match_payload(session, user, job) for job in jobs]
    items.sort(
        key=lambda item: (
            item["match_score"],
            item["posted_at"] or item["last_seen_at"],
        ),
        reverse=True,
    )
    return {
        "engine_version": ENGINE_VERSION,
        "disclaimer": (
            "ApplyAI uses verified candidate evidence and posting data to prioritize roles. "
            "The result is not a hiring probability."
        ),
        "items": items[:limit],
    }


@router.get("/matches/{job_id}")
def get_match(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return _match_payload(session, user, get_owned_job(job_id, session))


@router.get("/tailoring/{job_id}")
def get_tailoring_v1(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    payload = tailoring_payload(job=job, user=user, session=session)
    payload["safety"] = {
        "policy": "EVIDENCE_LOCKED",
        "message": (
            "Suggestions may reframe verified experience, but cannot add employers, "
            "responsibilities, skills, metrics, or outcomes."
        ),
    }
    return payload


@router.put("/tailoring/{job_id}")
def save_tailoring_v1(
    job_id: uuid.UUID,
    payload: TailoringWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return save_tailoring(
        job_id=job_id,
        payload=payload,
        user=user,
        session=session,
    )


@router.post("/tailoring/{job_id}/finalize")
def finalize_tailoring_v1(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)
    payload = tailoring_payload(job=job, user=user, session=session)
    approved = [item for item in payload["edits"] if item["decision"] == "APPROVED"]
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TAILORING_REVIEW_REQUIRED",
                "message": "Approve at least one evidence-backed edit before finalizing.",
            },
        )
    candidate = candidate_context(session, user)
    profile: CandidateProfile | None = candidate["profile"]
    experiences: list[CandidateExperience] = candidate["experiences"]
    company = session.get(Company, job.company_id)
    lines = [
        f"# Tailored resume for {job.title}",
        "",
        "## Professional summary",
        profile.summary if profile and profile.summary else "",
        "",
        "## Approved targeted language",
        *[f"- {item['text']}" for item in approved],
        "",
        "## Verified experience",
    ]
    for experience in experiences:
        lines.extend(
            [
                f"### {experience.title} — {experience.company_name}",
                experience.description or "",
            ]
        )
    lines.extend(
        [
            "",
            "## Application target",
            f"{job.title} at {company.canonical_name if company else 'Unknown company'}",
        ]
    )
    content = "\n".join(lines).strip()
    existing = session.scalar(
        select(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            ApplicationAnswer.question == FINAL_RESUME_KEY,
        )
    )
    if existing is None:
        session.add(
            ApplicationAnswer(
                application_id=application.id,
                user_id=user.id,
                question=FINAL_RESUME_KEY,
                answer=content,
                user_verified=True,
            )
        )
    else:
        existing.answer = content
        existing.user_verified = True
    session.commit()
    return {
        "application_id": application.id,
        "job_id": job.id,
        "status": "FINALIZED",
        "approved_edits": len(approved),
        "tailored_resume_markdown": content,
    }


def _question_drafts(
    session: Session, user: User, job: Job, match: dict
) -> list[dict]:
    candidate = candidate_context(session, user)
    profile: CandidateProfile | None = candidate["profile"]
    experiences: list[CandidateExperience] = candidate["experiences"]
    company = session.get(Company, job.company_id)
    company_name = company.canonical_name if company else "the company"
    experience = (
        experiences[0].description
        if experiences and experiences[0].description
        else profile.summary if profile and profile.summary else ""
    )
    skills = ", ".join(match["matched_skills"][:5]) or "my verified experience"
    return [
        {
            "question": "Why are you interested in this role?",
            "draft": (
                f"I am interested in the {job.title} role at {company_name} because it "
                f"aligns with my target direction and verified strengths in {skills}. "
                "I would welcome the opportunity to learn more about the team's priorities "
                "and expected first-year outcomes."
            ),
            "evidence": [
                "Selected role and company",
                "Saved candidate target direction",
                "Matched verified skills",
            ],
        },
        {
            "question": "What relevant experience should we know about?",
            "draft": (
                f"My most relevant verified experience is: {experience} "
                "I can provide additional context about my direct contribution and the result."
            ),
            "evidence": ["Most recent user-verified experience"],
        },
        {
            "question": "Why are you a strong fit?",
            "draft": (
                f"My profile directly supports {skills}. I also want to be transparent "
                f"about the areas to discuss: {'; '.join(match['risks'][:2])}"
            ),
            "evidence": [
                "Explainable match breakdown",
                "Verified candidate skills",
                "Identified fit risks",
            ],
        },
    ]


def _assistant_payload(session: Session, user: User, job: Job) -> dict:
    match = _match_payload(session, user, job)
    application = _application(session, user, job.id)
    candidate = candidate_context(session, user)
    profile: CandidateProfile | None = candidate["profile"]
    company = session.get(Company, job.company_id)
    company_name = company.canonical_name if company else "the company"

    persisted_questions: dict[str, ApplicationAnswer] = {}
    cover_row: ApplicationAnswer | None = None
    final_resume: str | None = None
    if application:
        for row in session.scalars(
            select(ApplicationAnswer).where(
                ApplicationAnswer.application_id == application.id
            )
        ):
            if row.question == COVER_LETTER_KEY:
                cover_row = row
            elif row.question.startswith(QUESTION_PREFIX):
                persisted_questions[row.question[len(QUESTION_PREFIX) :]] = row
            elif row.question == FINAL_RESUME_KEY:
                final_resume = row.answer

    questions = _question_drafts(session, user, job, match)
    for item in questions:
        saved = persisted_questions.get(item["question"])
        item["answer"] = saved.answer if saved else item["draft"]
        item["user_verified"] = saved.user_verified if saved else False

    summary = (
        profile.summary
        if profile and profile.summary
        else "my verified professional background"
    )
    skills = ", ".join(match["matched_skills"][:4]) or "the experience in my profile"
    cover_letter = (
        f"Dear {company_name} Hiring Team,\n\n"
        f"I am applying for the {job.title} position. {summary.rstrip('.')}.\n\n"
        f"My verified experience aligns most clearly through {skills}. I would value "
        "the opportunity to discuss how this background could support the role's priorities "
        "and where I would need to ramp up.\n\n"
        f"Thank you for your consideration.\n\nSincerely,\n{user.first_name or 'Candidate'}"
    )
    if cover_row:
        cover_letter = cover_row.answer

    profile_ready = bool(
        profile and candidate["skills"] and candidate["experiences"]
    )
    match_ready = match["match_score"] >= 60
    resume_ready = final_resume is not None
    cover_ready = bool(cover_row and cover_row.user_verified)
    questions_ready = bool(questions) and all(
        item["user_verified"] for item in questions
    )
    checklist = [
        {
            "id": "profile",
            "label": "Candidate profile has verified experience and skills",
            "complete": profile_ready,
            "weight": 20,
        },
        {
            "id": "match",
            "label": "Role fit meets the review threshold",
            "complete": match_ready,
            "weight": 20,
        },
        {
            "id": "resume",
            "label": "Tailored resume is finalized",
            "complete": resume_ready,
            "weight": 25,
        },
        {
            "id": "cover-letter",
            "label": "Cover letter is reviewed and verified",
            "complete": cover_ready,
            "weight": 15,
        },
        {
            "id": "questions",
            "label": "Application answers are reviewed and verified",
            "complete": questions_ready,
            "weight": 20,
        },
    ]
    readiness = sum(
        item["weight"] for item in checklist if item["complete"]
    )
    return {
        "application_id": application.id if application else None,
        "job_id": job.id,
        "job_title": job.title,
        "company_name": company_name,
        "match": match,
        "cover_letter": cover_letter,
        "cover_letter_verified": cover_ready,
        "questions": questions,
        "checklist": checklist,
        "readiness_score": readiness,
        "ready_to_finalize": readiness == 100,
        "source_url": match["source_url"],
        "external_submission_required": True,
        "notice": (
            "ApplyAI prepares and tracks the package. The candidate must review the "
            "content and submit it on the employer's site."
        ),
    }


@router.get("/application-assistant/{job_id}")
def get_assistant(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return _assistant_payload(session, user, get_owned_job(job_id, session))


@router.put("/application-assistant/{job_id}")
def save_assistant(
    job_id: uuid.UUID,
    payload: AssistantWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)
    match = _match_payload(session, user, job)
    allowed_questions = {
        item["question"] for item in _question_drafts(session, user, job, match)
    }
    if not {item.question for item in payload.answers}.issubset(allowed_questions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more application questions are invalid",
        )
    session.execute(
        delete(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            (
                (ApplicationAnswer.question == COVER_LETTER_KEY)
                | ApplicationAnswer.question.like(f"{QUESTION_PREFIX}%")
            ),
        )
    )
    session.add(
        ApplicationAnswer(
            application_id=application.id,
            user_id=user.id,
            question=COVER_LETTER_KEY,
            answer=payload.cover_letter.strip(),
            user_verified=payload.cover_letter_verified,
        )
    )
    for answer in payload.answers:
        session.add(
            ApplicationAnswer(
                application_id=application.id,
                user_id=user.id,
                question=f"{QUESTION_PREFIX}{answer.question}",
                answer=answer.answer.strip(),
                user_verified=answer.user_verified,
            )
        )
    session.commit()
    return _assistant_payload(session, user, job)


@router.post("/application-assistant/{job_id}/finalize")
def finalize_assistant(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)
    payload = _assistant_payload(session, user, job)
    if not payload["ready_to_finalize"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "APPLICATION_REVIEW_REQUIRED",
                "message": "Complete all candidate review steps before finalizing.",
                "incomplete": [
                    item["label"]
                    for item in payload["checklist"]
                    if not item["complete"]
                ],
            },
        )
    previous = application.current_status
    if previous != "READY":
        application.current_status = "READY"
        session.add(
            ApplicationEvent(
                application_id=application.id,
                actor_user_id=user.id,
                from_status=previous,
                to_status="READY",
                metadata_json={
                    "created_by": "application_assistant_v1",
                    "external_submission_required": True,
                },
            )
        )
    manifest = (
        f"Application package finalized for {payload['job_title']} at "
        f"{payload['company_name']}. Candidate review is complete; external submission "
        "is still required."
    )
    existing = session.scalar(
        select(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            ApplicationAnswer.question == PACKAGE_KEY,
        )
    )
    if existing:
        existing.answer = manifest
        existing.user_verified = True
    else:
        session.add(
            ApplicationAnswer(
                application_id=application.id,
                user_id=user.id,
                question=PACKAGE_KEY,
                answer=manifest,
                user_verified=True,
            )
        )
    session.commit()
    return {
        "application_id": application.id,
        "job_id": job.id,
        "current_status": "READY",
        "readiness_score": 100,
        "package_manifest": manifest,
        "source_url": payload["source_url"],
        "external_submission_required": True,
    }
