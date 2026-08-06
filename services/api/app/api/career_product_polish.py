from __future__ import annotations

import re
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import career_product as base
from app.api.candidate_workspace import (
    TAILORING_PREFIX,
    candidate_context,
    get_owned_job,
    tailoring_payload,
)
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import Application, ApplicationAnswer, Job, JobSkill, User


router = APIRouter(prefix="/career-v1", tags=["career intelligence v1 polish"])
MAX_SHORTLIST_ROLES_PER_COMPANY = 2


def _normalized(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _sentence(value: str | None) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if not text:
        return ""
    return text if text[-1] in ".!?" else f"{text}."


def _human_join(values: list[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _normalized(value)
        if value and key not in seen:
            seen.add(key)
            unique.append(value)
    if not unique:
        return "the verified experience in your profile"
    if len(unique) == 1:
        return unique[0]
    if len(unique) == 2:
        return f"{unique[0]} and {unique[1]}"
    return f"{', '.join(unique[:-1])}, and {unique[-1]}"


def _application(session: Session, user: User, job_id: uuid.UUID) -> Application | None:
    return session.scalar(
        select(Application).where(
            Application.user_id == user.id,
            Application.job_id == job_id,
        )
    )


def _has_persisted_answers(
    session: Session,
    application: Application | None,
    *,
    questions: tuple[str, ...],
    prefixes: tuple[str, ...] = (),
) -> bool:
    if application is None:
        return False
    rows = list(
        session.scalars(
            select(ApplicationAnswer).where(
                ApplicationAnswer.application_id == application.id
            )
        )
    )
    return any(
        row.question in questions
        or any(row.question.startswith(prefix) for prefix in prefixes)
        for row in rows
    )


@router.get("/matches")
def list_polished_matches(
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
    ranked = [base._match_payload(session, user, job) for job in jobs]
    ranked.sort(
        key=lambda item: (
            item["match_score"],
            item["posted_at"] or item["last_seen_at"],
        ),
        reverse=True,
    )

    shortlisted: list[dict] = []
    seen_role_company: set[tuple[str, str]] = set()
    company_counts: defaultdict[str, int] = defaultdict(int)
    for item in ranked:
        company_key = _normalized(item["company_name"])
        role_key = (company_key, _normalized(item["title"]))
        if role_key in seen_role_company:
            continue
        if company_counts[company_key] >= MAX_SHORTLIST_ROLES_PER_COMPANY:
            continue
        seen_role_company.add(role_key)
        company_counts[company_key] += 1
        shortlisted.append(item)
        if len(shortlisted) >= limit:
            break

    return {
        "engine_version": base.ENGINE_VERSION,
        "disclaimer": (
            "ApplyAI uses verified candidate evidence and posting data to prioritize roles. "
            "The result is not a hiring probability."
        ),
        "shortlist_policy": (
            "Equivalent title-and-company postings are grouped, and the shortlist shows "
            "no more than two roles per company."
        ),
        "items": shortlisted,
    }


@router.get("/tailoring/{job_id}")
def get_polished_tailoring(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    payload = tailoring_payload(job=job, user=user, session=session)
    candidate = candidate_context(session, user)
    candidate_skill_names = {
        item.normalized_name: item.name for item in candidate["skills"]
    }
    job_skills = list(
        session.scalars(
            select(JobSkill)
            .where(JobSkill.job_id == job.id)
            .order_by(JobSkill.required.desc(), JobSkill.name)
        )
    )
    matched_names = [
        candidate_skill_names[item.normalized_name]
        for item in job_skills
        if item.normalized_name in candidate_skill_names
    ]
    relevant_names = matched_names or [item.name for item in job_skills if item.required][:3]
    skills_phrase = _human_join(relevant_names[:4])

    application = _application(session, user, job.id)
    has_saved_edits = _has_persisted_answers(
        session,
        application,
        questions=(),
        prefixes=(f"{TAILORING_PREFIX}:",),
    )

    polished = {
        0: lambda current: (
            f"{_sentence(current)} The most relevant verified strengths for this role "
            f"include {skills_phrase}."
        ),
        1: lambda current: (
            f"{_sentence(current)} Verified strengths relevant to the {job.title} role "
            f"include {skills_phrase}."
        ),
        2: lambda current: _sentence(current),
    }
    evidence = {
        0: "Uses only the verified experience description and matched profile skills.",
        1: "Uses the verified profile summary, selected job title, and matched profile skills.",
        2: "Preserves the original verified wording without introducing a new claim.",
    }
    for edit in payload["edits"]:
        suggestion = polished.get(edit["index"], _sentence)(edit["current"])
        edit["suggested"] = suggestion
        edit["evidence"] = evidence.get(
            edit["index"],
            "Preserves verified candidate evidence.",
        )
        if not has_saved_edits:
            edit["text"] = suggestion

    payload["safety"] = {
        "policy": "EVIDENCE_LOCKED",
        "message": (
            "Suggestions may clarify verified experience, but cannot add employers, "
            "responsibilities, skills, metrics, or outcomes."
        ),
    }
    return payload


def _polished_question_answers(
    session: Session,
    user: User,
    job: Job,
    payload: dict,
) -> dict[str, str]:
    candidate = candidate_context(session, user)
    experience = next(
        (
            _sentence(item.description)
            for item in candidate["experiences"]
            if item.description
        ),
        "",
    )
    skills_phrase = _human_join(payload["match"]["matched_skills"][:5])
    missing_phrase = _human_join(payload["match"]["missing_skills"][:3])
    company_name = payload["company_name"]

    why_interested = (
        f"I am interested in the {job.title} role at {company_name} because it aligns "
        f"with my target direction and verified experience in {skills_phrase}. I would "
        "welcome the opportunity to understand the team's priorities, how success is "
        "measured in the first year, and where my background can contribute most quickly."
    )
    relevant_experience = (
        f"{experience} This is the strongest verified example of the scope and measurable "
        "results I have delivered."
        if experience
        else (
            "My verified profile summarizes the experience most relevant to this role. "
            "I would provide concrete examples and clarify my direct contribution during "
            "the interview process."
        )
    )
    if payload["match"]["missing_skills"]:
        strong_fit = (
            f"My strongest verified alignment is in {skills_phrase}. The posting also "
            f"mentions {missing_phrase}, which is not explicit in my current profile. I "
            "would clarify the expected depth during the interview and discuss only "
            "directly relevant experience I can support."
        )
    else:
        strong_fit = (
            f"My strongest verified alignment is in {skills_phrase}, supported by the "
            "experience and results in my profile. I would use the interview process to "
            "confirm team scope, priorities, and first-year expectations."
        )
    return {
        "Why are you interested in this role?": why_interested,
        "What relevant experience should we know about?": relevant_experience,
        "Why are you a strong fit?": strong_fit,
    }


@router.get("/application-assistant/{job_id}")
def get_polished_assistant(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    payload = base._assistant_payload(session, user, job)
    application = _application(session, user, job.id)
    has_saved_materials = _has_persisted_answers(
        session,
        application,
        questions=(base.COVER_LETTER_KEY,),
        prefixes=(base.QUESTION_PREFIX,),
    )
    if has_saved_materials:
        return payload

    candidate = candidate_context(session, user)
    profile = candidate["profile"]
    summary = _sentence(profile.summary if profile else None)
    experience = next(
        (
            _sentence(item.description)
            for item in candidate["experiences"]
            if item.description
        ),
        "",
    )
    skills_phrase = _human_join(payload["match"]["matched_skills"][:4])
    gap_sentence = ""
    if payload["match"]["missing_skills"]:
        gap_sentence = (
            " I would also welcome a discussion about the expected depth in "
            f"{_human_join(payload['match']['missing_skills'][:2])}, so I can describe "
            "my relevant experience accurately."
        )

    paragraphs = [
        f"Dear {payload['company_name']} Hiring Team,",
        (
            f"I am applying for the {job.title} position because it aligns with my "
            f"verified experience in {skills_phrase} and my next career direction."
        ),
        " ".join(part for part in (summary, experience) if part),
        (
            "I would value the opportunity to discuss how this background could support "
            f"the team's priorities.{gap_sentence}"
        ),
        "Thank you for your consideration.",
        f"Sincerely,\n{user.first_name or 'Candidate'}",
    ]
    payload["cover_letter"] = "\n\n".join(part for part in paragraphs if part)

    answers = _polished_question_answers(session, user, job, payload)
    for item in payload["questions"]:
        polished = answers.get(item["question"])
        if polished:
            item["draft"] = polished
            item["answer"] = polished
    return payload
