from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import (
    candidate_context,
    get_or_create_application,
    get_owned_job,
)
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import (
    Application,
    ApplicationAnswer,
    ApplicationEvent,
    CandidateExperience,
    CandidateProfile,
    CandidateSkill,
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

router = APIRouter(prefix="/career-ai", tags=["career intelligence"])

MATCH_ENGINE_VERSION = "explainable-match-v1"
TAILOR_PREFIX = "APPLYAI_TAILOR_V1"
ASSISTANT_PREFIX = "APPLYAI_ASSISTANT_V1"
FINAL_RESUME_KEY = f"{TAILOR_PREFIX}:FINAL_RESUME"
COVER_LETTER_KEY = f"{ASSISTANT_PREFIX}:COVER_LETTER"
PACKAGE_KEY = f"{ASSISTANT_PREFIX}:PACKAGE"


class TailoringDecisionWrite(BaseModel):
    edit_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=5000)
    decision: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"


class TailoringWrite(BaseModel):
    edits: list[TailoringDecisionWrite] = Field(min_length=1, max_length=20)


class AssistantAnswerWrite(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)
    user_verified: bool = False


class ApplicationAssistantWrite(BaseModel):
    cover_letter: str = Field(min_length=1, max_length=12000)
    cover_letter_verified: bool = False
    answers: list[AssistantAnswerWrite] = Field(default_factory=list, max_length=20)


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", value.lower())
        if len(token) > 2
    }


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _application_for_job(
    session: Session, user: User, job_id: uuid.UUID
) -> Application | None:
    return session.scalar(
        select(Application).where(
            Application.user_id == user.id,
            Application.job_id == job_id,
        )
    )


def _job_rows(session: Session, job: Job) -> dict:
    company = session.get(Company, job.company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
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


def _skill_match(
    candidate_skills: list[CandidateSkill],
    job_skills: list[JobSkill],
) -> tuple[list[str], list[str], int]:
    candidate_names = {item.normalized_name: item.name for item in candidate_skills}
    matched: list[str] = []
    missing: list[str] = []
    for job_skill in job_skills:
        normalized = job_skill.normalized_name
        if normalized in candidate_names:
            matched.append(job_skill.name)
            continue
        job_tokens = _tokens(job_skill.name)
        partial = any(
            job_tokens & _tokens(candidate_name)
            for candidate_name in candidate_names
        )
        if partial:
            matched.append(job_skill.name)
        elif job_skill.required:
            missing.append(job_skill.name)
    required_count = max(1, sum(1 for skill in job_skills if skill.required))
    matched_required = sum(
        1
        for skill in job_skills
        if skill.required and skill.name in matched
    )
    score = round(30 * matched_required / required_count)
    if not job_skills:
        score = 15
    return matched[:10], missing[:10], min(30, score)


def _match_detail(session: Session, user: User, job: Job) -> dict:
    context = candidate_context(session, user)
    profile: CandidateProfile | None = context["profile"]
    preference = context["preference"]
    rows = _job_rows(session, job)
    location: JobLocation | None = rows["location"]
    compensation: JobCompensation | None = rows["compensation"]
    job_skills: list[JobSkill] = rows["skills"]
    requirements: list[JobRequirement] = rows["requirements"]

    target_tokens = set(context["role_tokens"])
    title_tokens = _tokens(job.title)
    role_overlap = sorted(target_tokens & title_tokens)
    role_score = min(30, 10 + len(role_overlap) * 5) if role_overlap else 5

    matched_skills, missing_skills, skill_score = _skill_match(
        context["skills"], job_skills
    )

    preferred_modes = {
        mode.upper()
        for mode in (preference.work_modes if preference else [])
    }
    preferred_location = (
        _normalize(preference.location_text)
        if preference and preference.location_text
        else None
    )
    location_score = 7
    location_reason = "No location preference was supplied."
    if location is not None:
        mode = location.work_mode.upper()
        location_text = _normalize(location.location_text)
        if preferred_location and preferred_location in location_text:
            location_score = 15
            location_reason = "The posting location matches your saved preference."
        elif mode in preferred_modes:
            location_score = 13
            location_reason = "The work arrangement matches your saved preference."
        elif preferred_location or preferred_modes:
            location_score = 2
            location_reason = "The location or work arrangement is outside your first preference."

    compensation_score = 7
    compensation_reason = "Compensation fit could not be fully verified."
    minimum_target = preference.minimum_compensation if preference else None
    if minimum_target and compensation and compensation.maximum is not None:
        if compensation.maximum >= minimum_target:
            compensation_score = 15
            compensation_reason = "The published range can meet your minimum compensation target."
        else:
            compensation_score = 0
            compensation_reason = "The published range is below your minimum compensation target."
    elif minimum_target is None:
        compensation_score = 10
        compensation_reason = "No minimum compensation target is saved."

    seniority_score = 3
    seniority_reason = "Seniority fit needs recruiter confirmation."
    years = profile.years_experience if profile else None
    seniority = (job.seniority or "").upper()
    if years is not None:
        if seniority in {"MANAGER", "DIRECTOR", "LEAD", "SENIOR"} and years >= 7:
            seniority_score = 5
            seniority_reason = "Your verified years of experience support the stated seniority."
        elif seniority in {"ENTRY", "JUNIOR"} and years >= 7:
            seniority_score = 1
            seniority_reason = "The role may be below your current seniority."

    now = datetime.now(timezone.utc)
    last_seen = job.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    age_days = max(0, (now - last_seen).days)
    freshness_score = 5 if age_days <= 7 else 3 if age_days <= 30 else 1
    freshness_reason = (
        "The posting was verified within the last week."
        if age_days <= 7
        else f"The posting was last verified {age_days} days ago."
    )

    total = (
        role_score
        + skill_score
        + location_score
        + compensation_score
        + seniority_score
        + freshness_score
    )
    total = max(0, min(100, total))
    if total >= 80:
        decision = "PRIORITIZE"
        fit_band = "STRONG"
    elif total >= 65:
        decision = "CONSIDER"
        fit_band = "GOOD"
    elif total >= 50:
        decision = "STRETCH"
        fit_band = "PARTIAL"
    else:
        decision = "SKIP"
        fit_band = "WEAK"

    profile_signals = int(profile is not None) + int(bool(context["roles"])) + int(
        bool(context["skills"])
    )
    job_signals = int(bool(job_skills)) + int(location is not None) + int(
        compensation is not None
    )
    signal_count = profile_signals + job_signals
    confidence = "HIGH" if signal_count >= 6 else "MEDIUM" if signal_count >= 4 else "LOW"

    candidate_document = " ".join(
        [
            profile.summary if profile and profile.summary else "",
            profile.current_title if profile and profile.current_title else "",
            " ".join(item.description or "" for item in context["experiences"]),
            " ".join(item.name for item in context["skills"]),
        ]
    )
    candidate_tokens = _tokens(candidate_document)
    missing_requirements: list[str] = []
    for requirement in requirements:
        requirement_tokens = _tokens(requirement.text)
        if requirement.required and requirement_tokens and not (
            requirement_tokens & candidate_tokens
        ):
            missing_requirements.append(requirement.text)

    strengths: list[str] = []
    if role_overlap:
        strengths.append(
            f"Target-role alignment is visible through: {', '.join(role_overlap[:4])}."
        )
    if matched_skills:
        strengths.append(
            f"Verified skill alignment includes {', '.join(matched_skills[:5])}."
        )
    if location_score >= 13:
        strengths.append(location_reason)
    if compensation_score == 15:
        strengths.append(compensation_reason)
    if not strengths:
        strengths.append("The role is active, but the saved profile provides limited direct evidence.")

    risks: list[str] = []
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
        risks.append("Validate team scope, reporting line, and first-year expectations.")

    breakdown = [
        {
            "factor": "ROLE_ALIGNMENT",
            "score": role_score,
            "maximum": 30,
            "reason": (
                f"Matched title concepts: {', '.join(role_overlap)}."
                if role_overlap
                else "No strong title overlap was found."
            ),
        },
        {
            "factor": "SKILLS",
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

    company: Company = rows["company"]
    saved = (
        session.get(SavedJob, {"user_id": user.id, "job_id": job.id}) is not None
    )
    return {
        "job_id": job.id,
        "title": job.title,
        "company_name": company.canonical_name,
        "location": location.location_text if location else None,
        "work_mode": location.work_mode if location else None,
        "minimum_compensation": compensation.minimum if compensation else None,
        "maximum_compensation": compensation.maximum if compensation else None,
        "posted_at": job.posted_at,
        "last_seen_at": job.last_seen_at,
        "saved": saved,
        "match_score": total,
        "fit_band": fit_band,
        "decision": decision,
        "confidence": confidence,
        "engine_version": MATCH_ENGINE_VERSION,
        "summary": (
            f"{decision.title()}: {total}% fit with {confidence.lower()} confidence. "
            "The score is an explainable prioritization aid, not a hiring prediction."
        ),
        "strengths": strengths[:5],
        "risks": risks[:5],
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "missing_requirements": missing_requirements[:5],
        "breakdown": breakdown,
        "source_url": rows["source_url"],
        "description": job.description,
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
    items = [_match_detail(session, user, job) for job in jobs]
    items.sort(
        key=lambda item: (
            item["match_score"],
            item["posted_at"] or item["last_seen_at"],
        ),
        reverse=True,
    )
    return {
        "engine_version": MATCH_ENGINE_VERSION,
        "disclaimer": (
            "Scores rank opportunities using saved candidate evidence and job data. "
            "They do not predict employer decisions."
        ),
        "items": items[:limit],
    }


@router.get("/matches/{job_id}")
def get_match(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    return _match_detail(session, user, job)


def _tailoring_templates(session: Session, user: User, job: Job) -> list[dict]:
    context = candidate_context(session, user)
    rows = _job_rows(session, job)
    profile: CandidateProfile | None = context["profile"]
    experiences: list[CandidateExperience] = context["experiences"]
    candidate_skills: list[CandidateSkill] = context["skills"]
    match = _match_detail(session, user, job)

    matched = match["matched_skills"]
    visible_skills = ", ".join(matched[:5]) or ", ".join(
        item.name for item in candidate_skills[:5]
    )
    summary = (
        profile.summary
        if profile and profile.summary
        else "Add a verified professional summary before finalizing this resume."
    )
    first = experiences[0] if experiences else None
    second = experiences[1] if len(experiences) > 1 else None
    first_text = (
        first.description
        if first and first.description
        else "Add a verified achievement from your most recent role."
    )
    second_text = (
        second.description
        if second and second.description
        else first_text
    )
    company: Company = rows["company"]

    templates = [
        {
            "edit_id": "summary",
            "section": "PROFESSIONAL_SUMMARY",
            "original_text": summary,
            "suggested_text": (
                f"{summary.rstrip('.')} Relevant verified strengths for the "
                f"{job.title} opportunity include {visible_skills}."
            ),
            "evidence": [
                "Candidate profile summary",
                "User-verified candidate skills",
                f"Selected posting: {job.title} at {company.canonical_name}",
            ],
        },
        {
            "edit_id": "experience-primary",
            "section": "EXPERIENCE",
            "original_text": first_text,
            "suggested_text": (
                f"{first_text.rstrip('.')} Highlight this work where it demonstrates "
                f"{visible_skills}, without changing the original scope or metrics."
            ),
            "evidence": [
                "Most recent user-verified experience description",
                "Matched job skills",
            ],
        },
        {
            "edit_id": "experience-secondary",
            "section": "EXPERIENCE",
            "original_text": second_text,
            "suggested_text": (
                f"{second_text.rstrip('.')} Connect the verified outcome to the "
                f"role's need for {visible_skills}, without adding new claims."
            ),
            "evidence": [
                "User-verified experience description",
                "Matched job skills",
            ],
        },
        {
            "edit_id": "skills",
            "section": "SKILLS",
            "original_text": ", ".join(item.name for item in candidate_skills),
            "suggested_text": (
                "Prioritize these verified skills for this application: "
                + (visible_skills or "complete your candidate skills first")
                + "."
            ),
            "evidence": [
                "Only user-verified skills are included",
                "Ordering reflects the selected posting",
            ],
        },
    ]
    for template in templates:
        template["unsupported_claims"] = []
        template["decision"] = "PENDING"
        template["text"] = template["suggested_text"]
    return templates


def _load_tailoring_answers(
    session: Session, application: Application | None
) -> dict[str, dict]:
    if application is None:
        return {}
    persisted: dict[str, dict] = {}
    for answer in session.scalars(
        select(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            ApplicationAnswer.question.like(f"{TAILOR_PREFIX}:EDIT:%"),
        )
    ):
        parts = answer.question.split(":", 4)
        if len(parts) != 5:
            continue
        edit_id = parts[3]
        decision = parts[4]
        persisted[edit_id] = {
            "text": answer.answer,
            "decision": decision,
            "user_verified": answer.user_verified,
        }
    return persisted


def _tailoring_payload(session: Session, user: User, job: Job) -> dict:
    application = _application_for_job(session, user, job.id)
    persisted = _load_tailoring_answers(session, application)
    edits = _tailoring_templates(session, user, job)
    for edit in edits:
        stored = persisted.get(edit["edit_id"])
        if stored:
            edit["text"] = stored["text"]
            edit["decision"] = stored["decision"]
    final_resume = None
    if application is not None:
        final_row = session.scalar(
            select(ApplicationAnswer).where(
                ApplicationAnswer.application_id == application.id,
                ApplicationAnswer.question == FINAL_RESUME_KEY,
            )
        )
        final_resume = final_row.answer if final_row else None
    company = session.get(Company, job.company_id)
    return {
        "job_id": job.id,
        "application_id": application.id if application else None,
        "job_title": job.title,
        "company_name": company.canonical_name if company else "Unknown company",
        "edits": edits,
        "finalized": final_resume is not None,
        "tailored_resume_markdown": final_resume,
        "safety": {
            "policy": "EVIDENCE_LOCKED",
            "message": (
                "ApplyAI may reframe verified evidence, but it must not add employers, "
                "skills, responsibilities, metrics, or outcomes that are not in the profile."
            ),
        },
    }


@router.get("/tailoring/{job_id}")
def get_tailoring_v1(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    return _tailoring_payload(session, user, job)


@router.put("/tailoring/{job_id}")
def save_tailoring_v1(
    job_id: uuid.UUID,
    payload: TailoringWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)
    allowed = {item["edit_id"] for item in _tailoring_templates(session, user, job)}
    supplied = {item.edit_id for item in payload.edits}
    if not supplied.issubset(allowed):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more tailoring edits are invalid",
        )
    session.execute(
        delete(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            ApplicationAnswer.question.like(f"{TAILOR_PREFIX}:EDIT:%"),
        )
    )
    for item in payload.edits:
        session.add(
            ApplicationAnswer(
                application_id=application.id,
                user_id=user.id,
                question=f"{TAILOR_PREFIX}:EDIT:{item.edit_id}:{item.decision}",
                answer=item.text.strip(),
                user_verified=item.decision == "APPROVED",
            )
        )
    session.commit()
    return _tailoring_payload(session, user, job)


@router.post("/tailoring/{job_id}/finalize")
def finalize_tailoring(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)
    payload = _tailoring_payload(session, user, job)
    approved = [
        edit for edit in payload["edits"] if edit["decision"] == "APPROVED"
    ]
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TAILORING_REVIEW_REQUIRED",
                "message": "Approve at least one evidence-backed edit before finalizing.",
            },
        )
    context = candidate_context(session, user)
    profile: CandidateProfile | None = context["profile"]
    experiences: list[CandidateExperience] = context["experiences"]
    company = session.get(Company, job.company_id)
    lines = [
        f"# Tailored resume for {job.title}",
        f"## Candidate summary",
        profile.summary if profile and profile.summary else "",
        "",
        "## Approved targeted language",
    ]
    lines.extend(f"- {edit['text']}" for edit in approved)
    if experiences:
        lines.extend(["", "## Verified experience"])
        for experience in experiences:
            lines.append(
                f"### {experience.title} — {experience.company_name}\n"
                f"{experience.description or ''}"
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
        existing = ApplicationAnswer(
            application_id=application.id,
            user_id=user.id,
            question=FINAL_RESUME_KEY,
            answer=content,
            user_verified=True,
        )
        session.add(existing)
    else:
        existing.answer = content
        existing.user_verified = True
    session.commit()
    return {
        "application_id": application.id,
        "job_id": job.id,
        "approved_edits": len(approved),
        "tailored_resume_markdown": content,
        "status": "FINALIZED",
    }


def _assistant_questions(
    session: Session, user: User, job: Job, match: dict
) -> list[dict]:
    context = candidate_context(session, user)
    profile: CandidateProfile | None = context["profile"]
    experiences: list[CandidateExperience] = context["experiences"]
    company = session.get(Company, job.company_id)
    company_name = company.canonical_name if company else "the company"
    primary_experience = experiences[0] if experiences else None
    experience_text = (
        primary_experience.description
        if primary_experience and primary_experience.description
        else profile.summary if profile and profile.summary else ""
    )
    skill_text = ", ".join(match["matched_skills"][:5]) or "the verified skills in my profile"
    return [
        {
            "question": "Why are you interested in this role?",
            "draft": (
                f"I am interested in the {job.title} role at {company_name} because it "
                f"aligns with my verified experience and target direction. The strongest "
                f"overlap is in {skill_text}. I would use an interview to understand the "
                "team's priorities, scope, and expected first-year outcomes."
            ),
            "evidence": [
                "Selected role and company",
                "Saved target direction",
                "Matched verified skills",
            ],
        },
        {
            "question": "What relevant experience should we know about?",
            "draft": (
                f"My most relevant verified experience is: {experience_text} "
                "I would be glad to explain the context, my direct contribution, and the "
                "results in more detail."
            ),
            "evidence": ["Most recent user-verified experience"],
        },
        {
            "question": "Why are you a strong fit?",
            "draft": (
                f"My profile directly supports {skill_text}. ApplyAI also identified "
                f"the following areas to discuss honestly: {'; '.join(match['risks'][:2])}"
            ),
            "evidence": [
                "Explainable match result",
                "Verified candidate skills",
                "Identified fit risks",
            ],
        },
    ]


def _assistant_persisted(
    session: Session, application: Application | None
) -> tuple[dict[str, ApplicationAnswer], ApplicationAnswer | None]:
    if application is None:
        return {}, None
    answers: dict[str, ApplicationAnswer] = {}
    cover: ApplicationAnswer | None = None
    for row in session.scalars(
        select(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            ApplicationAnswer.question.like(f"{ASSISTANT_PREFIX}:%"),
        )
    ):
        if row.question == COVER_LETTER_KEY:
            cover = row
        elif row.question.startswith(f"{ASSISTANT_PREFIX}:QUESTION:"):
            original_question = row.question.split(":", 3)[-1]
            answers[original_question] = row
    return answers, cover


def _assistant_payload(session: Session, user: User, job: Job) -> dict:
    match = _match_detail(session, user, job)
    context = candidate_context(session, user)
    profile: CandidateProfile | None = context["profile"]
    company = session.get(Company, job.company_id)
    company_name = company.canonical_name if company else "the company"
    application = _application_for_job(session, user, job.id)
    persisted_answers, persisted_cover = _assistant_persisted(session, application)
    questions = _assistant_questions(session, user, job, match)
    for question in questions:
        persisted = persisted_answers.get(question["question"])
        question["answer"] = persisted.answer if persisted else question["draft"]
        question["user_verified"] = persisted.user_verified if persisted else False

    first_name = user.first_name or "Candidate"
    profile_summary = (
        profile.summary
        if profile and profile.summary
        else "my verified professional background"
    )
    matched = ", ".join(match["matched_skills"][:4]) or "the skills shown in my profile"
    cover_letter = (
        f"Dear {company_name} Hiring Team,\n\n"
        f"I am applying for the {job.title} position. {profile_summary.rstrip('.')}.\n\n"
        f"My verified experience aligns most clearly through {matched}. "
        f"I am particularly interested in discussing how this background could support "
        f"the role's priorities while being transparent about the areas that would "
        f"require ramp-up.\n\n"
        f"Thank you for your consideration.\n\nSincerely,\n{first_name}"
    )
    if persisted_cover:
        cover_letter = persisted_cover.answer

    final_resume = None
    if application is not None:
        final_resume = session.scalar(
            select(ApplicationAnswer.answer).where(
                ApplicationAnswer.application_id == application.id,
                ApplicationAnswer.question == FINAL_RESUME_KEY,
            )
        )
    verified_questions = sum(1 for item in questions if item["user_verified"])
    readiness = 0
    checklist = []
    profile_ready = profile is not None and bool(context["skills"]) and bool(context["experiences"])
    checklist.append(
        {
            "id": "profile",
            "label": "Candidate profile has verified experience and skills",
            "complete": profile_ready,
        }
    )
    if profile_ready:
        readiness += 20
    match_ready = match["match_score"] >= 60
    checklist.append(
        {
            "id": "match",
            "label": "Role fit has been reviewed",
            "complete": match_ready,
        }
    )
    if match_ready:
        readiness += 20
    resume_ready = final_resume is not None
    checklist.append(
        {
            "id": "resume",
            "label": "Tailored resume has been finalized",
            "complete": resume_ready,
        }
    )
    if resume_ready:
        readiness += 25
    cover_ready = persisted_cover is not None and persisted_cover.user_verified
    checklist.append(
        {
            "id": "cover-letter",
            "label": "Cover letter has been reviewed and verified",
            "complete": cover_ready,
        }
    )
    if cover_ready:
        readiness += 15
    questions_ready = bool(questions) and verified_questions == len(questions)
    checklist.append(
        {
            "id": "questions",
            "label": "Application answers have been reviewed and verified",
            "complete": questions_ready,
        }
    )
    if questions_ready:
        readiness += 20

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
        "external_submission_required": True,
        "source_url": match["source_url"],
        "notice": (
            "ApplyAI prepares and tracks the application package. The candidate must "
            "review all content and submit on the employer's site."
        ),
    }


@router.get("/application-assistant/{job_id}")
def get_application_assistant(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    return _assistant_payload(session, user, job)


@router.put("/application-assistant/{job_id}")
def save_application_assistant(
    job_id: uuid.UUID,
    payload: ApplicationAssistantWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)
    expected_questions = {
        item["question"] for item in _assistant_questions(
            session, user, job, _match_detail(session, user, job)
        )
    }
    supplied_questions = {item.question for item in payload.answers}
    if not supplied_questions.issubset(expected_questions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more application questions are invalid",
        )
    session.execute(
        delete(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            ApplicationAnswer.question.like(f"{ASSISTANT_PREFIX}:%"),
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
    for item in payload.answers:
        session.add(
            ApplicationAnswer(
                application_id=application.id,
                user_id=user.id,
                question=f"{ASSISTANT_PREFIX}:QUESTION:{item.question}",
                answer=item.answer.strip(),
                user_verified=item.user_verified,
            )
        )
    session.commit()
    return _assistant_payload(session, user, job)


@router.post("/application-assistant/{job_id}/finalize")
def finalize_application_package(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)
    payload = _assistant_payload(session, user, job)
    if not payload["ready_to_finalize"]:
        incomplete = [
            item["label"] for item in payload["checklist"] if not item["complete"]
        ]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "APPLICATION_REVIEW_REQUIRED",
                "message": "Complete the application review before finalizing.",
                "incomplete": incomplete,
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
        f"{payload['company_name']}. Candidate review complete. "
        "External submission is still required."
    )
    existing = session.scalar(
        select(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            ApplicationAnswer.question == PACKAGE_KEY,
        )
    )
    if existing is None:
        session.add(
            ApplicationAnswer(
                application_id=application.id,
                user_id=user.id,
                question=PACKAGE_KEY,
                answer=manifest,
                user_verified=True,
            )
        )
    else:
        existing.answer = manifest
        existing.user_verified = True
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
