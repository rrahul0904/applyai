import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import get_owned_job
from app.core.auth import get_current_user
from app.core.database import get_session
from app.growth_models import RecruiterLensCriteriaSet
from app.models import User
from app.recruiter_lens import ALLOWED_MODES, build_recruiter_lens

router = APIRouter(prefix="/recruiter-lens", tags=["recruiter lens"])


@router.get("/jobs/{job_id}")
def get_recruiter_lens(
    job_id: uuid.UUID,
    mode: str = Query(default="DEFAULT_RECRUITER"),
    criteria_set_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    normalized_mode = mode.upper()
    if normalized_mode not in ALLOWED_MODES:
        raise HTTPException(status_code=422, detail="Unsupported Recruiter Lens perspective")
    custom_criteria = None
    resolved_set_id = None
    if criteria_set_id is not None:
        criteria_set = session.scalar(
            select(RecruiterLensCriteriaSet).where(
                RecruiterLensCriteriaSet.id == criteria_set_id,
                RecruiterLensCriteriaSet.user_id == user.id,
                RecruiterLensCriteriaSet.archived.is_(False),
            )
        )
        if criteria_set is None:
            raise HTTPException(status_code=404, detail="Recruiter Lens criteria set not found")
        custom_criteria = list(criteria_set.criteria_json or [])
        normalized_mode = criteria_set.mode if criteria_set.mode in ALLOWED_MODES else "CUSTOM"
        resolved_set_id = str(criteria_set.id)
    return build_recruiter_lens(
        session,
        user,
        job,
        mode=normalized_mode,
        custom_criteria=custom_criteria,
        criteria_set_id=resolved_set_id,
    )
