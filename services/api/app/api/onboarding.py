from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import CandidatePreference, CandidateProfile, CandidateTargetRole, User
from app.schemas import OnboardingStateResponse, OnboardingStateWrite


router = APIRouter(prefix="/onboarding", tags=["onboarding"])
STAGES = [
    "ACCOUNT_CREATED",
    "RESUME",
    "RESUME_PROCESSING",
    "PROFILE_REVIEW",
    "TARGET_ROLES",
    "LOCATION",
    "WORK_PREFERENCES",
    "COMPENSATION",
    "REVIEW",
    "COMPLETE",
]

# Resume processing is optional because candidates may continue manually without a resume.
FORWARD_TRANSITIONS = {
    "ACCOUNT_CREATED": {"RESUME"},
    "RESUME": {"RESUME_PROCESSING", "PROFILE_REVIEW"},
    "RESUME_PROCESSING": {"PROFILE_REVIEW"},
    "PROFILE_REVIEW": {"TARGET_ROLES"},
    "TARGET_ROLES": {"LOCATION"},
    "LOCATION": {"WORK_PREFERENCES"},
    "WORK_PREFERENCES": {"COMPENSATION"},
    "COMPENSATION": {"REVIEW"},
    "REVIEW": {"COMPLETE"},
    "COMPLETE": set(),
}


def onboarding_completion_error(user: User, session: Session) -> str | None:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None or not (profile.current_title or profile.headline):
        return "Add a current title or professional headline before completing onboarding"

    target_role_count = session.scalar(
        select(func.count(CandidateTargetRole.id)).where(CandidateTargetRole.user_id == user.id)
    ) or 0
    if target_role_count < 1:
        return "Select at least one target role before completing onboarding"

    preference = session.scalar(
        select(CandidatePreference).where(CandidatePreference.user_id == user.id)
    )
    if preference is None or not preference.work_modes:
        return "Select at least one work preference before completing onboarding"
    return None


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

    current_stage = user.onboarding_stage if user.onboarding_stage in STAGES else "ACCOUNT_CREATED"
    current_index = STAGES.index(current_stage)
    requested_index = STAGES.index(stage)

    # Candidates may return to an earlier step to correct data, but forward progress must
    # follow the persisted workflow so refreshes and returning sessions remain deterministic.
    if requested_index > current_index and stage not in FORWARD_TRANSITIONS[current_stage]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ONBOARDING_STAGE_OUT_OF_ORDER",
                "message": "Complete the current onboarding step first",
            },
        )

    if stage == "COMPLETE":
        completion_error = onboarding_completion_error(user, session)
        if completion_error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ONBOARDING_INCOMPLETE", "message": completion_error},
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
