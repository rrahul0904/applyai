from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from statistics import median
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import candidate_context, get_owned_job
from app.core.auth import get_current_user
from app.core.database import get_session
from app.growth_models import (
    CandidatePortfolio,
    CandidatePortfolioProject,
    InterviewPracticeAttempt,
    RecruiterLensCriteriaSet,
)
from app.models import (
    CandidateEducation,
    CandidateExperience,
    CandidateProfile,
    CandidateSkill,
    CandidateTargetRole,
    Job,
    JobCompensation,
    JobLocation,
    JobRequirement,
    JobSkill,
    User,
)

router = APIRouter(prefix="/growth", tags=["candidate growth"])

_ALLOWED_THEMES = {"PROFESSIONAL", "MINIMAL", "TECHNICAL", "PORTFOLIO"}
_ALLOWED_MODES = {"DEFAULT_RECRUITER", "STRICT_MUST_HAVE", "HIRING_MANAGER", "TECHNICAL", "CUSTOM"}
_ALLOWED_PRACTICE = {"BEHAVIORAL", "TECHNICAL", "SYSTEM_DESIGN", "SQL", "CODING"}
_DEFAULT_VISIBILITY = {
    "headline": True,
    "about": True,
    "experience": True,
    "education": True,
    "skills": True,
    "projects": True,
    "resume": False,
    "contact_links": False,
}
_PROTECTED_CRITERIA = {
    "race", "color", "religion", "sex", "gender", "sexual orientation", "pregnancy",
    "disability", "age", "national origin", "ethnicity", "marital status", "genetic",
    "salary history", "criminal record",
}
_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])?$")


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value else None


def _clean_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not (3 <= len(slug) <= 80) or not _SLUG.match(slug):
        raise HTTPException(status_code=422, detail="Portfolio slug must be 3-80 lowercase letters, numbers, or hyphens")
    return slug


def _url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    if not (cleaned.startswith("https://") or cleaned.startswith("http://")):
        raise HTTPException(status_code=422, detail="Public links must use HTTP or HTTPS")
    return cleaned


def _portfolio(session: Session, user: User) -> CandidatePortfolio | None:
    return session.scalar(select(CandidatePortfolio).where(CandidatePortfolio.user_id == user.id))


def _portfolio_payload(session: Session, portfolio: CandidatePortfolio) -> dict[str, Any]:
    projects = list(session.scalars(
        select(CandidatePortfolioProject)
        .where(CandidatePortfolioProject.user_id == portfolio.user_id)
        .order_by(CandidatePortfolioProject.project_date.desc().nullslast(), CandidatePortfolioProject.created_at.desc())
    ).all())
    return {
        "id": str(portfolio.id),
        "slug": portfolio.slug,
        "public_path": f"/u/{portfolio.slug}",
        "published": portfolio.published,
        "theme": portfolio.theme,
        "indexing_allowed": portfolio.indexing_allowed,
        "headline": portfolio.headline,
        "about": portfolio.about,
        "visibility": {**_DEFAULT_VISIBILITY, **(portfolio.visibility_json or {})},
        "contact_enabled": portfolio.contact_enabled,
        "projects": [_project_payload(item) for item in projects],
        "updated_at": _iso(portfolio.updated_at),
    }


def _project_payload(project: CandidatePortfolioProject) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "title": project.title,
        "summary": project.summary,
        "role": project.role,
        "technologies": project.technologies or [],
        "verified_outcome": project.verified_outcome,
        "project_url": project.project_url,
        "repository_url": project.repository_url,
        "media_url": project.media_url,
        "project_date": _iso(project.project_date),
        "visible": project.visible,
    }


class PortfolioWrite(BaseModel):
    slug: str = Field(min_length=3, max_length=80)
    published: bool = False
    theme: str = "PROFESSIONAL"
    indexing_allowed: bool = False
    headline: str | None = Field(default=None, max_length=240)
    about: str | None = Field(default=None, max_length=4000)
    visibility: dict[str, bool] = Field(default_factory=dict)
    contact_enabled: bool = False

    @field_validator("theme")
    @classmethod
    def valid_theme(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in _ALLOWED_THEMES:
            raise ValueError("Unsupported portfolio theme")
        return normalized


class ProjectWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=4000)
    role: str | None = Field(default=None, max_length=240)
    technologies: list[str] = Field(default_factory=list, max_length=30)
    verified_outcome: str | None = Field(default=None, max_length=2000)
    project_url: str | None = None
    repository_url: str | None = None
    media_url: str | None = None
    project_date: date | None = None
    visible: bool = True


class CriterionWrite(BaseModel):
    label: str = Field(min_length=2, max_length=300)
    required: bool = True
    weight: float = Field(default=1.0, ge=0.1, le=5.0)


class CriteriaSetWrite(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    mode: str = "CUSTOM"
    criteria: list[CriterionWrite] = Field(default_factory=list, max_length=12)

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in _ALLOWED_MODES:
            raise ValueError("Unsupported Recruiter Lens mode")
        return normalized


class AttemptWrite(BaseModel):
    job_id: uuid.UUID | None = None
    category: Literal["BEHAVIORAL", "TECHNICAL", "SYSTEM_DESIGN", "SQL", "CODING"]
    question: str = Field(min_length=3, max_length=2000)
    answer_text: str | None = Field(default=None, max_length=12000)
    notes: str | None = Field(default=None, max_length=4000)
    self_review: dict[str, Any] = Field(default_factory=dict)


def _criterion_is_safe(label: str) -> bool:
    normalized = " ".join(re.findall(r"[a-z0-9]+", label.casefold()))
    return not any(term in normalized for term in _PROTECTED_CRITERIA)


@router.get("/portfolio")
def get_portfolio(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    portfolio = _portfolio(session, user)
    if portfolio is None:
        suggested = re.sub(r"[^a-z0-9]+", "-", (user.first_name or "candidate").casefold()).strip("-") or "candidate"
        return {
            "configured": False,
            "suggested_slug": f"{suggested}-{str(user.id)[:6]}",
            "published": False,
            "theme": "PROFESSIONAL",
            "visibility": _DEFAULT_VISIBILITY,
            "projects": [],
        }
    return {"configured": True, **_portfolio_payload(session, portfolio)}


@router.put("/portfolio")
def put_portfolio(payload: PortfolioWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    slug = _clean_slug(payload.slug)
    collision = session.scalar(select(CandidatePortfolio).where(CandidatePortfolio.slug == slug, CandidatePortfolio.user_id != user.id))
    if collision is not None:
        raise HTTPException(status_code=409, detail="That public portfolio slug is already in use")
    visibility = {**_DEFAULT_VISIBILITY, **{key: bool(value) for key, value in payload.visibility.items() if key in _DEFAULT_VISIBILITY}}
    portfolio = _portfolio(session, user)
    if portfolio is None:
        portfolio = CandidatePortfolio(user_id=user.id, slug=slug)
        session.add(portfolio)
    portfolio.slug = slug
    portfolio.published = payload.published
    portfolio.theme = payload.theme
    portfolio.indexing_allowed = payload.indexing_allowed
    portfolio.headline = payload.headline.strip() if payload.headline else None
    portfolio.about = payload.about.strip() if payload.about else None
    portfolio.visibility_json = visibility
    portfolio.contact_enabled = payload.contact_enabled
    session.commit()
    session.refresh(portfolio)
    return _portfolio_payload(session, portfolio)


@router.get("/portfolio/projects")
def list_projects(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = session.scalars(select(CandidatePortfolioProject).where(CandidatePortfolioProject.user_id == user.id).order_by(CandidatePortfolioProject.created_at.desc())).all()
    return [_project_payload(row) for row in rows]


@router.post("/portfolio/projects", status_code=201)
def create_project(payload: ProjectWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    project = CandidatePortfolioProject(
        user_id=user.id,
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        role=payload.role.strip() if payload.role else None,
        technologies=[item.strip() for item in payload.technologies if item.strip()][:30],
        verified_outcome=payload.verified_outcome.strip() if payload.verified_outcome else None,
        project_url=_url(payload.project_url),
        repository_url=_url(payload.repository_url),
        media_url=_url(payload.media_url),
        project_date=payload.project_date,
        visible=payload.visible,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return _project_payload(project)


@router.put("/portfolio/projects/{project_id}")
def update_project(project_id: uuid.UUID, payload: ProjectWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    project = session.scalar(select(CandidatePortfolioProject).where(CandidatePortfolioProject.id == project_id, CandidatePortfolioProject.user_id == user.id))
    if project is None:
        raise HTTPException(status_code=404, detail="Portfolio project not found")
    project.title = payload.title.strip()
    project.summary = payload.summary.strip()
    project.role = payload.role.strip() if payload.role else None
    project.technologies = [item.strip() for item in payload.technologies if item.strip()][:30]
    project.verified_outcome = payload.verified_outcome.strip() if payload.verified_outcome else None
    project.project_url = _url(payload.project_url)
    project.repository_url = _url(payload.repository_url)
    project.media_url = _url(payload.media_url)
    project.project_date = payload.project_date
    project.visible = payload.visible
    session.commit()
    session.refresh(project)
    return _project_payload(project)


@router.delete("/portfolio/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> None:
    project = session.scalar(select(CandidatePortfolioProject).where(CandidatePortfolioProject.id == project_id, CandidatePortfolioProject.user_id == user.id))
    if project is None:
        raise HTTPException(status_code=404, detail="Portfolio project not found")
    session.delete(project)
    session.commit()


@router.get("/public/portfolio/{slug}")
def public_portfolio(slug: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    portfolio = session.scalar(select(CandidatePortfolio).where(CandidatePortfolio.slug == slug, CandidatePortfolio.published.is_(True)))
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Public portfolio not found")
    visibility = {**_DEFAULT_VISIBILITY, **(portfolio.visibility_json or {})}
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == portfolio.user_id))
    experiences: list[CandidateExperience] = []
    education: list[CandidateEducation] = []
    skills: list[CandidateSkill] = []
    if profile is not None:
        if visibility["experience"]:
            experiences = list(session.scalars(select(CandidateExperience).where(CandidateExperience.profile_id == profile.id).order_by(CandidateExperience.start_date.desc().nullslast())).all())
        if visibility["education"]:
            education = list(session.scalars(select(CandidateEducation).where(CandidateEducation.profile_id == profile.id).order_by(CandidateEducation.end_date.desc().nullslast())).all())
        if visibility["skills"]:
            skills = list(session.scalars(select(CandidateSkill).where(CandidateSkill.profile_id == profile.id).order_by(CandidateSkill.name)).all())
    projects = list(session.scalars(select(CandidatePortfolioProject).where(CandidatePortfolioProject.user_id == portfolio.user_id, CandidatePortfolioProject.visible.is_(True)).order_by(CandidatePortfolioProject.project_date.desc().nullslast())).all()) if visibility["projects"] else []
    return {
        "slug": portfolio.slug,
        "theme": portfolio.theme,
        "indexing_allowed": portfolio.indexing_allowed,
        "headline": portfolio.headline if visibility["headline"] else None,
        "about": portfolio.about if visibility["about"] else None,
        "profile": {
            "current_title": profile.current_title if profile else None,
            "summary": profile.summary if profile and visibility["about"] and not portfolio.about else None,
        },
        "experience": [
            {"company_name": row.company_name, "title": row.title, "start_date": _iso(row.start_date), "end_date": _iso(row.end_date), "description": row.description}
            for row in experiences
        ],
        "education": [
            {"institution": row.institution, "degree": row.degree, "field_of_study": row.field_of_study, "start_date": _iso(row.start_date), "end_date": _iso(row.end_date)}
            for row in education
        ],
        "skills": [row.name for row in skills],
        "projects": [_project_payload(row) for row in projects],
        "contact_enabled": portfolio.contact_enabled,
        "privacy": {"candidate_opt_in": True, "raw_resume_exposed": False, "indexing_allowed": portfolio.indexing_allowed},
    }


def _market_jobs(session: Session, target: str) -> list[Job]:
    tokens = [token for token in re.findall(r"[a-z0-9]+", target.casefold()) if len(token) > 1]
    statement = select(Job).where(Job.status == "ACTIVE", Job.data_origin != "DEVELOPMENT_SEED")
    if tokens:
        statement = statement.where(Job.normalized_title.ilike(f"%{' '.join(tokens[:4])}%"))
    rows = list(session.scalars(statement.order_by(Job.posted_at.desc().nullslast()).limit(500)).all())
    if not rows and tokens:
        rows = list(session.scalars(select(Job).where(Job.status == "ACTIVE", Job.data_origin != "DEVELOPMENT_SEED", Job.normalized_title.ilike(f"%{tokens[0]}%")).order_by(Job.posted_at.desc().nullslast()).limit(500)).all())
    return rows


@router.get("/career-navigation")
def career_navigation(target_role: str | None = Query(default=None, max_length=240), user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    candidate = candidate_context(session, user)
    profile = candidate["profile"]
    roles = list(candidate["roles"])
    chosen = (target_role or (roles[0].title if roles else None) or (profile.current_title if profile else None) or "").strip()
    if not chosen:
        raise HTTPException(status_code=409, detail="Add a current or target role to use Career Navigation")
    jobs = _market_jobs(session, chosen)
    job_ids = [job.id for job in jobs]
    skills = list(session.scalars(select(JobSkill).where(JobSkill.job_id.in_(job_ids))).all()) if job_ids else []
    locations = list(session.scalars(select(JobLocation).where(JobLocation.job_id.in_(job_ids))).all()) if job_ids else []
    compensation = list(session.scalars(select(JobCompensation).where(JobCompensation.job_id.in_(job_ids))).all()) if job_ids else []
    requirements = list(session.scalars(select(JobRequirement).where(JobRequirement.job_id.in_(job_ids))).all()) if job_ids else []
    skill_counts = Counter(skill.normalized_name for skill in skills if skill.normalized_name)
    skill_labels = {skill.normalized_name: skill.name for skill in skills}
    candidate_skills = {skill.normalized_name for skill in candidate["skills"] if skill.normalized_name}
    top_skills = [{"skill": skill_labels.get(name, name), "posting_count": count, "evidenced": name in candidate_skills} for name, count in skill_counts.most_common(20)]
    missing = [item for item in top_skills if not item["evidenced"]][:10]
    title_counts = Counter(job.title for job in jobs)
    adjacent = [
        {"role": title, "posting_count": count, "reason": f"Appears in the same current job sample as your target role and shares its requirement/skill market."}
        for title, count in title_counts.most_common(8) if title.casefold() != chosen.casefold()
    ][:5]
    work_modes = Counter(location.work_mode for location in locations if location.work_mode)
    location_counts = Counter(location.location_text for location in locations if location.location_text)
    seniority = Counter(job.seniority for job in jobs if job.seniority)
    salary_rows = [row for row in compensation if row.currency == "USD" and row.interval == "YEAR" and (row.minimum is not None or row.maximum is not None)]
    salary_midpoints = [((row.minimum or row.maximum or 0) + (row.maximum or row.minimum or 0)) / 2 for row in salary_rows]
    newest = max((job.last_seen_at for job in jobs), default=None)
    requirement_words = Counter()
    for requirement in requirements:
        for token in re.findall(r"[a-z][a-z0-9+#.-]{2,}", requirement.text.casefold()):
            if token not in {"the", "and", "with", "for", "from", "that", "this", "years", "experience", "required", "preferred"}:
                requirement_words[token] += 1
    return {
        "current_role": profile.current_title if profile else None,
        "target_role": chosen,
        "target_roles": [role.title for role in roles],
        "adjacent_roles": adjacent,
        "evidence_strengths": [item for item in top_skills if item["evidenced"]][:10],
        "skill_gaps": missing,
        "preparation": [f"Build a truthful example or learning plan around {item['skill']}; it appears in {item['posting_count']} sampled postings." for item in missing[:5]],
        "market": {
            "sample_size": len(jobs),
            "freshest_observation": _iso(newest),
            "coverage_caveat": "This reflects ApplyAI's current canonical job corpus, not the entire labor market.",
            "work_modes": dict(work_modes.most_common()),
            "locations": [{"location": name, "count": count} for name, count in location_counts.most_common(8)],
            "seniority": dict(seniority.most_common()),
            "top_skills": top_skills[:12],
            "common_requirement_terms": [{"term": name, "count": count} for name, count in requirement_words.most_common(10)],
            "salary": {
                "sample_size": len(salary_midpoints),
                "median_explicit_usd_yearly_midpoint": round(median(salary_midpoints)) if salary_midpoints else None,
                "inferred": False,
            },
        },
    }


def _criteria_payload(row: RecruiterLensCriteriaSet) -> dict[str, Any]:
    return {"id": str(row.id), "name": row.name, "mode": row.mode, "criteria": row.criteria_json or [], "archived": row.archived, "updated_at": _iso(row.updated_at)}


@router.get("/recruiter-lens/criteria-sets")
def list_criteria_sets(include_archived: bool = False, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    statement = select(RecruiterLensCriteriaSet).where(RecruiterLensCriteriaSet.user_id == user.id)
    if not include_archived:
        statement = statement.where(RecruiterLensCriteriaSet.archived.is_(False))
    return [_criteria_payload(row) for row in session.scalars(statement.order_by(RecruiterLensCriteriaSet.updated_at.desc())).all()]


@router.post("/recruiter-lens/criteria-sets", status_code=201)
def create_criteria_set(payload: CriteriaSetWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    criteria = [item.model_dump() for item in payload.criteria]
    unsafe = [item["label"] for item in criteria if not _criterion_is_safe(item["label"])]
    if unsafe:
        raise HTTPException(status_code=422, detail={"code": "PROTECTED_CRITERION_BLOCKED", "message": "Recruiter Lens self-assessment criteria must be job-relevant and cannot target protected characteristics."})
    duplicate = session.scalar(select(RecruiterLensCriteriaSet).where(RecruiterLensCriteriaSet.user_id == user.id, func.lower(RecruiterLensCriteriaSet.name) == payload.name.strip().casefold()))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="A criteria set with that name already exists")
    row = RecruiterLensCriteriaSet(user_id=user.id, name=payload.name.strip(), mode=payload.mode, criteria_json=criteria)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _criteria_payload(row)


@router.put("/recruiter-lens/criteria-sets/{set_id}")
def update_criteria_set(set_id: uuid.UUID, payload: CriteriaSetWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.scalar(select(RecruiterLensCriteriaSet).where(RecruiterLensCriteriaSet.id == set_id, RecruiterLensCriteriaSet.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Criteria set not found")
    criteria = [item.model_dump() for item in payload.criteria]
    if any(not _criterion_is_safe(item["label"]) for item in criteria):
        raise HTTPException(status_code=422, detail={"code": "PROTECTED_CRITERION_BLOCKED", "message": "Recruiter Lens self-assessment criteria must be job-relevant and cannot target protected characteristics."})
    row.name = payload.name.strip()
    row.mode = payload.mode
    row.criteria_json = criteria
    session.commit()
    session.refresh(row)
    return _criteria_payload(row)


@router.post("/recruiter-lens/criteria-sets/{set_id}/archive")
def archive_criteria_set(set_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.scalar(select(RecruiterLensCriteriaSet).where(RecruiterLensCriteriaSet.id == set_id, RecruiterLensCriteriaSet.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Criteria set not found")
    row.archived = True
    session.commit()
    session.refresh(row)
    return _criteria_payload(row)


def _practice_questions(session: Session, job: Job) -> list[dict[str, str]]:
    skills = list(session.scalars(select(JobSkill).where(JobSkill.job_id == job.id).order_by(JobSkill.required.desc(), JobSkill.name).limit(8)).all())
    requirements = list(session.scalars(select(JobRequirement).where(JobRequirement.job_id == job.id).order_by(JobRequirement.required.desc()).limit(6)).all())
    result: list[dict[str, str]] = []
    result.append({"category": "BEHAVIORAL", "question": f"Tell me about a project most relevant to {job.title}. What was your specific contribution and a result you can support with evidence?"})
    for skill in skills[:3]:
        result.append({"category": "TECHNICAL", "question": f"Explain how you have used {skill.name} in practice. If you have not used it directly, explain the closest truthful experience and the gap."})
    result.append({"category": "SYSTEM_DESIGN", "question": f"Design a production system relevant to a {job.title} role. State assumptions, interfaces, failure modes, observability, and trade-offs."})
    if any("sql" in skill.normalized_name.casefold() or "data" in skill.normalized_name.casefold() for skill in skills):
        result.append({"category": "SQL", "question": "Given customers(customer_id) and orders(order_id, customer_id, amount, ordered_at), write and explain a query that returns each customer's latest order and lifetime spend."})
    else:
        result.append({"category": "SQL", "question": "Explain when a window function is preferable to GROUP BY, and give a practical example from analytics or application data."})
    result.append({"category": "CODING", "question": "Describe an efficient approach to deduplicate a stream of records by stable key while preserving the newest version. Discuss complexity and edge cases before writing code."})
    for requirement in requirements[:2]:
        result.append({"category": "BEHAVIORAL", "question": f"The posting asks for: {requirement.text[:240]}. What verified example would you use to demonstrate or truthfully contextualize this requirement?"})
    return result[:10]


@router.get("/interview-lab/jobs/{job_id}")
def interview_lab(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    job = get_owned_job(job_id, session)
    attempts = list(session.scalars(select(InterviewPracticeAttempt).where(InterviewPracticeAttempt.user_id == user.id, InterviewPracticeAttempt.job_id == job_id).order_by(InterviewPracticeAttempt.created_at.desc()).limit(50)).all())
    return {
        "job_id": str(job.id),
        "job_title": job.title,
        "questions": _practice_questions(session, job),
        "attempts": [_attempt_payload(row) for row in attempts],
        "execution_policy": {"remote_arbitrary_code_execution": False, "reason": "The $0 launch uses a safe answer workspace and reasoning prompts instead of an unsafe paid execution sandbox."},
    }


def _attempt_payload(row: InterviewPracticeAttempt) -> dict[str, Any]:
    return {"id": str(row.id), "job_id": str(row.job_id) if row.job_id else None, "category": row.category, "question": row.question, "answer_text": row.answer_text, "notes": row.notes, "self_review": row.self_review_json or {}, "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at)}


@router.post("/interview-lab/attempts", status_code=201)
def create_attempt(payload: AttemptWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    if payload.category not in _ALLOWED_PRACTICE:
        raise HTTPException(status_code=422, detail="Unsupported practice category")
    if payload.job_id is not None:
        get_owned_job(payload.job_id, session)
    row = InterviewPracticeAttempt(user_id=user.id, job_id=payload.job_id, category=payload.category, question=payload.question.strip(), answer_text=payload.answer_text.strip() if payload.answer_text else None, notes=payload.notes.strip() if payload.notes else None, self_review_json=payload.self_review)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _attempt_payload(row)


@router.get("/interview-lab/attempts")
def list_attempts(job_id: uuid.UUID | None = None, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    statement = select(InterviewPracticeAttempt).where(InterviewPracticeAttempt.user_id == user.id)
    if job_id is not None:
        statement = statement.where(InterviewPracticeAttempt.job_id == job_id)
    return [_attempt_payload(row) for row in session.scalars(statement.order_by(InterviewPracticeAttempt.created_at.desc()).limit(100)).all()]
