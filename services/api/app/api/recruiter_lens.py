import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.candidate_workspace import get_owned_job
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import User
from app.recruiter_lens import build_recruiter_lens

router = APIRouter(prefix="/recruiter-lens", tags=["recruiter lens"])


@router.get("/jobs/{job_id}")
def get_recruiter_lens(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    return build_recruiter_lens(session, user, job)
