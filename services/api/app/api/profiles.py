import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import (
    CandidateEducation,
    CandidateExperience,
    CandidatePreference,
    CandidateProfile,
    CandidateSkill,
    CandidateTargetRole,
    User,
)
from app.schemas import (
    EducationWrite,
    ExperienceWrite,
    ProfileResponse,
    ProfileReviewWrite,
    SkillWrite,
)


router = APIRouter(prefix="/profile", tags=["candidate profile"])


def response_for(
    profile: CandidateProfile,
    preference: CandidatePreference | None,
    roles: list[CandidateTargetRole],
    experiences: list[CandidateExperience],
    education: list[CandidateEducation],
    skills: list[CandidateSkill],
) -> ProfileResponse:
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        headline=profile.headline,
        current_title=profile.current_title,
        summary=profile.summary,
        years_experience=profile.years_experience,
        target_roles=[role.title for role in roles],
        location_text=preference.location_text if preference else None,
        work_modes=preference.work_modes if preference else [],
        minimum_compensation=preference.minimum_compensation if preference else None,
        experiences=[
            ExperienceWrite(
                id=item.id,
                company_name=item.company_name,
                title=item.title,
                start_date=item.start_date.isoformat() if item.start_date else None,
                end_date=item.end_date.isoformat() if item.end_date else None,
                description=item.description,
                provenance=item.provenance,
            )
            for item in experiences
        ],
        education=[
            EducationWrite(
                id=item.id,
                institution=item.institution,
                degree=item.degree,
                field_of_study=item.field_of_study,
                start_date=item.start_date.isoformat() if item.start_date else None,
                end_date=item.end_date.isoformat() if item.end_date else None,
                provenance=item.provenance,
            )
            for item in education
        ],
        skills=[
            SkillWrite(id=item.id, name=item.name, provenance=item.provenance)
            for item in skills
        ],
    )


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def profile_children(session: Session, profile_id: uuid.UUID):
    experiences = list(
        session.scalars(
            select(CandidateExperience)
            .where(CandidateExperience.profile_id == profile_id)
            .order_by(CandidateExperience.start_date.desc().nullslast())
        )
    )
    education = list(
        session.scalars(
            select(CandidateEducation)
            .where(CandidateEducation.profile_id == profile_id)
            .order_by(CandidateEducation.start_date.desc().nullslast())
        )
    )
    skills = list(
        session.scalars(
            select(CandidateSkill)
            .where(CandidateSkill.profile_id == profile_id)
            .order_by(CandidateSkill.name)
        )
    )
    return experiences, education, skills


@router.get("", response_model=ProfileResponse | None)
def get_profile(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProfileResponse | None:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None:
        return None
    preference = session.scalar(
        select(CandidatePreference).where(CandidatePreference.user_id == user.id)
    )
    roles = list(
        session.scalars(
            select(CandidateTargetRole)
            .where(CandidateTargetRole.user_id == user.id)
            .order_by(CandidateTargetRole.priority)
        )
    )
    experiences, education, skills = profile_children(session, profile.id)
    return response_for(profile, preference, roles, experiences, education, skills)


def save_profile(
    *,
    payload: ProfileReviewWrite,
    user: User,
    session: Session,
    commit: bool,
) -> ProfileResponse:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        session.add(profile)
    profile.headline = payload.headline
    profile.current_title = payload.current_title
    profile.summary = payload.summary
    profile.years_experience = payload.years_experience
    session.flush()

    preference = session.scalar(
        select(CandidatePreference).where(CandidatePreference.user_id == user.id)
    )
    if preference is None:
        preference = CandidatePreference(user_id=user.id)
        session.add(preference)
    preference.location_text = payload.location_text
    preference.work_modes = [mode.upper() for mode in payload.work_modes]
    preference.minimum_compensation = payload.minimum_compensation

    session.execute(delete(CandidateTargetRole).where(CandidateTargetRole.user_id == user.id))
    roles = [
        CandidateTargetRole(
            id=uuid.uuid4(),
            user_id=user.id,
            title=title.strip(),
            normalized_title=title.strip().lower(),
            priority=index,
        )
        for index, title in enumerate(payload.target_roles, start=1)
        if title.strip()
    ]
    session.add_all(roles)
    session.execute(
        delete(CandidateExperience).where(CandidateExperience.profile_id == profile.id)
    )
    session.execute(
        delete(CandidateEducation).where(CandidateEducation.profile_id == profile.id)
    )
    session.execute(delete(CandidateSkill).where(CandidateSkill.profile_id == profile.id))
    experiences = [
        CandidateExperience(
            id=uuid.uuid4(),
            profile_id=profile.id,
            company_name=item.company_name.strip(),
            title=item.title.strip(),
            start_date=parse_date(item.start_date),
            end_date=parse_date(item.end_date),
            description=item.description,
            provenance="USER_VERIFIED",
        )
        for item in payload.experiences
    ]
    education = [
        CandidateEducation(
            id=uuid.uuid4(),
            profile_id=profile.id,
            institution=item.institution.strip(),
            degree=item.degree,
            field_of_study=item.field_of_study,
            start_date=parse_date(item.start_date),
            end_date=parse_date(item.end_date),
            provenance="USER_VERIFIED",
        )
        for item in payload.education
    ]
    skills = [
        CandidateSkill(
            id=uuid.uuid4(),
            profile_id=profile.id,
            name=item.name.strip(),
            normalized_name=item.name.strip().lower(),
            provenance="USER_VERIFIED",
        )
        for item in payload.skills
        if item.name.strip()
    ]
    session.add_all([*experiences, *education, *skills])
    session.flush()
    if commit:
        session.commit()
        session.refresh(profile)
    return response_for(profile, preference, roles, experiences, education, skills)


@router.put("", response_model=ProfileResponse)
def put_profile(
    payload: ProfileReviewWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProfileResponse:
    return save_profile(payload=payload, user=user, session=session, commit=True)
