from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.semantic_matching import rerank
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import CandidatePreference, CandidateProfile, CandidateSkill, CandidateTargetRole, Company, Job, User

router = APIRouter(prefix="/semantic-matches", tags=["semantic matching"])


def _candidate_text(session: Session, user: User) -> str:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    roles = list(session.scalars(select(CandidateTargetRole.title).where(CandidateTargetRole.user_id == user.id).order_by(CandidateTargetRole.priority)))
    preference = session.scalar(select(CandidatePreference).where(CandidatePreference.user_id == user.id))
    skills: list[str] = []
    if profile:
        skills = list(session.scalars(select(CandidateSkill.name).where(CandidateSkill.profile_id == profile.id)))
    parts = [
        profile.headline if profile else None,
        profile.current_title if profile else None,
        profile.summary if profile else None,
        "Target roles: " + ", ".join(roles) if roles else None,
        "Skills: " + ", ".join(skills) if skills else None,
        f"Location: {preference.location_text}" if preference and preference.location_text else None,
        "Work modes: " + ", ".join(preference.work_modes) if preference and preference.work_modes else None,
    ]
    return "\n".join(part for part in parts if part)


@router.get("")
def semantic_matches(
    limit: int = Query(default=25, ge=1, le=100),
    candidate_pool: int = Query(default=120, ge=25, le=300),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    candidate_text = _candidate_text(session, user)
    rows = session.execute(
        select(Job, Company)
        .join(Company, Company.id == Job.company_id)
        .where(Job.status == "ACTIVE")
        .order_by(Job.posted_at.desc().nullslast(), Job.updated_at.desc())
        .limit(candidate_pool)
    ).all()
    documents = [
        (
            str(job.id),
            f"{job.title}\n{company.canonical_name}\n{job.description}\n{job.employment_type or ''}\n{job.seniority or ''}",
        )
        for job, company in rows
    ]
    scores = dict(rerank(candidate_text, documents)) if candidate_text and documents else {}
    by_id = {str(job.id): (job, company) for job, company in rows}
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    return {
        "engine": "embedding-reranker-v1",
        "items": [
            {
                "job_id": job_id,
                "semantic_score": score,
                "title": by_id[job_id][0].title,
                "company": by_id[job_id][1].canonical_name,
                "posted_at": by_id[job_id][0].posted_at,
                "explanation": "Semantic similarity between verified candidate goals/skills and the job description; this is prioritization, not hiring probability.",
            }
            for job_id, score in ranked
        ],
    }
