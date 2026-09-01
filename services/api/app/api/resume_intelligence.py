from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import candidate_context, get_owned_job
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import JobRequirement, JobSkill, ResumeExtraction, ResumeVersion, User

router = APIRouter(prefix="/resume-intelligence", tags=["resume intelligence"])

_GENERIC_PHRASES = (
    "results-driven",
    "hard-working",
    "team player",
    "go-getter",
    "detail-oriented",
    "responsible for",
)


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9+#.-]+", value.casefold()) if len(token) > 1}


@router.get("")
def resume_intelligence(
    job_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    version = session.scalar(
        select(ResumeVersion)
        .where(ResumeVersion.user_id == user.id)
        .order_by(ResumeVersion.created_at.desc(), ResumeVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise HTTPException(status_code=409, detail="Upload a resume before running Resume Intelligence")
    extraction = session.scalar(
        select(ResumeExtraction)
        .where(ResumeExtraction.resume_version_id == version.id)
        .order_by(ResumeExtraction.created_at.desc())
        .limit(1)
    )
    text = extraction.extracted_text if extraction and extraction.extracted_text else ""
    structured = extraction.structured_data if extraction and isinstance(extraction.structured_data, dict) else {}
    candidate = candidate_context(session, user)
    candidate_skills = {skill.normalized_name for skill in candidate["skills"] if skill.normalized_name}
    text_tokens = _tokens(text)
    section_candidates = {
        "experience": bool(structured.get("experience") or structured.get("experiences") or "experience" in text_tokens),
        "education": bool(structured.get("education") or "education" in text_tokens),
        "skills": bool(structured.get("skills") or "skills" in text_tokens),
    }
    generic_hits = [phrase for phrase in _GENERIC_PHRASES if phrase in text.casefold()]
    words = re.findall(r"\S+", text)
    verified_skills_in_text = [name for name in candidate_skills if name and name in text.casefold()]

    requirement_coverage: list[dict[str, Any]] = []
    if job_id is not None:
        job = get_owned_job(job_id, session)
        skills = list(session.scalars(select(JobSkill).where(JobSkill.job_id == job.id).order_by(JobSkill.required.desc())).all())
        requirements = list(session.scalars(select(JobRequirement).where(JobRequirement.job_id == job.id).order_by(JobRequirement.required.desc())).all())
        for skill in skills[:12]:
            requirement_coverage.append({
                "label": skill.name,
                "required": skill.required,
                "evidenced_in_candidate_profile": skill.normalized_name in candidate_skills,
                "visible_in_resume_text": skill.normalized_name in text.casefold(),
            })
        for requirement in requirements[:6]:
            requirement_tokens = _tokens(requirement.text)
            overlap = len(requirement_tokens & text_tokens) / max(1, len(requirement_tokens))
            requirement_coverage.append({
                "label": requirement.text[:300],
                "required": requirement.required,
                "evidenced_in_candidate_profile": None,
                "visible_in_resume_text": overlap >= 0.25,
            })

    checks = [
        {
            "id": "parseability",
            "label": "Parseability",
            "status": "PASS" if extraction and extraction.status == "COMPLETED" and bool(text) else "NEEDS_ATTENTION",
            "detail": "A bounded parser produced readable text." if text else "ApplyAI does not yet have readable extracted text for this version.",
        },
        {
            "id": "section-completeness",
            "label": "Section completeness",
            "status": "PASS" if all(section_candidates.values()) else "NEEDS_ATTENTION",
            "detail": f"Detected sections: {', '.join(name for name, present in section_candidates.items() if present) or 'none'}.",
        },
        {
            "id": "verified-skill-visibility",
            "label": "Verified skill visibility",
            "status": "PASS" if verified_skills_in_text else "NEEDS_ATTENTION",
            "detail": f"{len(verified_skills_in_text)} verified profile skills are explicit in the extracted resume text.",
        },
        {
            "id": "generic-language",
            "label": "Generic language",
            "status": "PASS" if len(generic_hits) <= 1 else "NEEDS_ATTENTION",
            "detail": "No heavy generic-language pattern detected." if len(generic_hits) <= 1 else f"Consider replacing generic phrases with defensible evidence: {', '.join(generic_hits[:4])}.",
        },
        {
            "id": "length-readability",
            "label": "Length / readability",
            "status": "PASS" if 150 <= len(words) <= 1800 else "NEEDS_ATTENTION",
            "detail": f"Extracted resume contains approximately {len(words)} words; ApplyAI flags only extreme length, not a universal ideal.",
        },
        {
            "id": "unsupported-claims",
            "label": "Unsupported claims",
            "status": "REVIEW_REQUIRED",
            "detail": "ApplyAI will not silently certify every resume sentence as verified. Review job-specific edits against Career Memory before finalizing.",
        },
    ]
    return {
        "resume_version_id": str(version.id),
        "filename": version.filename,
        "parser_status": extraction.status if extraction else None,
        "word_count": len(words),
        "checks": checks,
        "job_requirement_coverage": requirement_coverage,
        "policy": {
            "ats_probability": False,
            "hiring_probability": False,
            "unsupported_claims_are_not_auto_verified": True,
            "deterministic": True,
        },
    }
