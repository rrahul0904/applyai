from __future__ import annotations

from collections import Counter
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import Company, Job, JobCompensation, JobLocation, JobRequirement, JobSkill, User

router = APIRouter(prefix="/company-intelligence", tags=["company intelligence"])


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


@router.get("/jobs/{job_id}")
def company_intelligence_for_job(
    job_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    company = session.get(Company, job.company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    jobs = list(session.scalars(select(Job).where(Job.company_id == company.id).order_by(Job.posted_at.desc().nullslast())))
    job_ids = [item.id for item in jobs]
    active = [item for item in jobs if item.status == "ACTIVE"]
    skills = list(session.scalars(select(JobSkill.name).where(JobSkill.job_id.in_(job_ids)))) if job_ids else []
    locations = list(session.scalars(select(JobLocation).where(JobLocation.job_id.in_(job_ids)))) if job_ids else []
    compensations = list(session.scalars(select(JobCompensation).where(JobCompensation.job_id.in_(job_ids)))) if job_ids else []
    requirements = list(session.scalars(select(JobRequirement.text).where(JobRequirement.job_id.in_(job_ids)))) if job_ids else []
    descriptions = [item.description for item in jobs]
    corpus = "\n".join([*requirements, *descriptions])
    skill_counts = Counter(skill for skill in skills if skill)
    work_modes = Counter(location.work_mode for location in locations if location.work_mode)
    seniority = Counter(item.seniority for item in jobs if item.seniority)
    employment_types = Counter(item.employment_type for item in jobs if item.employment_type)
    min_values = [row.minimum for row in compensations if row.minimum is not None]
    max_values = [row.maximum for row in compensations if row.maximum is not None]

    sponsorship_signal = "UNKNOWN"
    if _contains(corpus, ("visa sponsorship", "sponsorship available", "will sponsor", "sponsor visa")):
        sponsorship_signal = "MENTIONED_AVAILABLE"
    elif _contains(corpus, ("no sponsorship", "unable to sponsor", "will not sponsor", "without sponsorship")):
        sponsorship_signal = "MENTIONED_UNAVAILABLE"

    return {
        "company_id": company.id,
        "company_name": company.canonical_name,
        "evidence_basis": "public_job_postings",
        "active_job_count": len(active),
        "known_job_count": len(jobs),
        "latest_posted_at": max((item.posted_at for item in jobs if item.posted_at), default=None),
        "work_modes": dict(work_modes),
        "seniority_mix": dict(seniority),
        "employment_type_mix": dict(employment_types),
        "top_skills": [{"name": name, "job_mentions": count} for name, count in skill_counts.most_common(15)],
        "compensation": {
            "observed_minimum": min(min_values) if min_values else None,
            "observed_maximum": max(max_values) if max_values else None,
            "postings_with_compensation": len(compensations),
        },
        "signals": {
            "visa_sponsorship": sponsorship_signal,
            "remote_language_present": _contains(corpus, ("remote", "work from home", "distributed team")),
            "ai_language_present": _contains(corpus, ("artificial intelligence", "machine learning", "generative ai", "large language model", "llm")),
            "leadership_hiring_present": any((item.seniority or "").upper() in {"MANAGER", "DIRECTOR", "VP", "EXECUTIVE"} for item in active),
        },
        "disclaimer": "Signals are derived only from ApplyAI's currently known public or first-party job postings and should not be treated as company-wide policy unless the source explicitly says so.",
    }
