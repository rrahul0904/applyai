from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import User
from app.schemas import OnboardingStateResponse, OnboardingStateWrite


router = APIRouter(prefix="/onboarding", tags=["onboarding"])
STAGES = [
    "ACCOUNT_CREATED",
    "RESUME",
    "PROFILE_REVIEW",
    "TARGET_ROLES",
    "WORK_PREFERENCES",
    "COMPENSATION",
    "COMPLETE",
]


@router.get("", response_model=OnboardingStateResponse)
def get_onboarding(user: User = Depends(get_current_user)) -> OnboardingStateResponse:
    return OnboardingStateResponse(
        onboarding_stage=user.onboarding_stage,
        onboarding_completed=user.onboarding_completed,
    )


@router.put("", response_model=OnboardingStateResponse)
def update_onboarding(
    payload: OnboardingStateWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> OnboardingStateResponse:
    stage = payload.stage.upper()
    if stage not in STAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_ONBOARDING_STAGE", "message": "Invalid onboarding stage"},
        )
    current_index = STAGES.index(user.onboarding_stage)
    requested_index = STAGES.index(stage)
    if requested_index > current_index + 1 and stage != "COMPLETE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ONBOARDING_STAGE_OUT_OF_ORDER",
                "message": "Complete the current onboarding step first",
            },
        )
    user.onboarding_stage = stage
    user.onboarding_completed = stage == "COMPLETE"
    session.add(user)
    session.commit()
    session.refresh(user)
    return OnboardingStateResponse(
        onboarding_stage=user.onboarding_stage,
        onboarding_completed=user.onboarding_completed,
    )
