import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.candidate_workspace import TailoringWrite, save_tailoring
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import User


router = APIRouter(prefix="/career-v1", tags=["career intelligence v1"])

SAFETY_CONTRACT = {
    "policy": "EVIDENCE_LOCKED",
    "message": (
        "Suggestions may reframe verified experience, but cannot add employers, "
        "responsibilities, skills, metrics, or outcomes."
    ),
}


@router.put("/tailoring/{job_id}")
def save_tailoring_with_contract(
    job_id: uuid.UUID,
    payload: TailoringWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    response = save_tailoring(
        job_id=job_id,
        payload=payload,
        user=user,
        session=session,
    )
    response["safety"] = SAFETY_CONTRACT
    return response
