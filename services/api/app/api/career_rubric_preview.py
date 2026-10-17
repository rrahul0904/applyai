from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.context import build_career_ai_context, get_owned_active_job
from app.career_rubric import DEFAULT_CAREER_RUBRIC, assess_career_rubric
from app.career_rubric_adapter import build_rubric_inputs_from_career_context
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import User

router = APIRouter(prefix="/career-v2", tags=["career rubric intelligence"])


@router.get("/jobs/{job_id}/rubric-assessment-preview")
def rubric_assessment_preview(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Return a deterministic, non-persistent evidence-linked rubric preview."""

    job = get_owned_active_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    context = build_career_ai_context(session, user, job)
    bundle = build_rubric_inputs_from_career_context(context)
    assessment = assess_career_rubric(
        candidate_revision=bundle.candidate_revision,
        job_revision=bundle.job_revision,
        requirements=bundle.requirements,
        evidence=bundle.evidence,
    )

    classified_ids = {requirement.id for requirement in bundle.requirements}
    unclassified = []
    for raw_requirement in context["job"].get("requirements") or []:
        requirement_id = f"job.requirement.{raw_requirement['id']}"
        if requirement_id in classified_ids:
            continue
        unclassified.append(
            {
                "id": requirement_id,
                "text": raw_requirement["text"],
                "required": raw_requirement["required"],
                "reason": (
                    "Free-text role requirements need an explicit rubric-dimension "
                    "classification before deterministic assessment."
                ),
            }
        )

    return {
        "mode": "DETERMINISTIC_PREVIEW",
        "assessment": asdict(assessment),
        "rubric": asdict(DEFAULT_CAREER_RUBRIC),
        "unclassified_job_requirements": unclassified,
        "limitations": [
            (
                "Only exact user-verified structured skill matches are auto-linked in "
                "this baseline."
            ),
            (
                "Leadership, autonomy, business accountability, scale, and seniority "
                "are not inferred from titles or free text."
            ),
            (
                "This preview is candidate coaching evidence; it is not a hiring "
                "probability or employer decision."
            ),
        ],
    }
