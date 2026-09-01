from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import get_owned_job
from app.core.auth import get_current_user
from app.core.database import get_session
from app.growth_models import RecruiterLensCriteriaSet
from app.models import Job, User
from app.recruiter_lens import ALLOWED_MODES, build_recruiter_lens
from app.recruiter_lens_report_models import RecruiterLensReportShare

router = APIRouter(prefix="/recruiter-lens", tags=["recruiter lens"])


def _criteria_for_user(
    session: Session,
    user: User,
    criteria_set_id: uuid.UUID | None,
) -> tuple[list[dict] | None, str | None, str | None]:
    if criteria_set_id is None:
        return None, None, None
    criteria_set = session.scalar(
        select(RecruiterLensCriteriaSet).where(
            RecruiterLensCriteriaSet.id == criteria_set_id,
            RecruiterLensCriteriaSet.user_id == user.id,
            RecruiterLensCriteriaSet.archived.is_(False),
        )
    )
    if criteria_set is None:
        raise HTTPException(status_code=404, detail="Recruiter Lens criteria set not found")
    mode = criteria_set.mode if criteria_set.mode in ALLOWED_MODES else "CUSTOM"
    return list(criteria_set.criteria_json or []), mode, str(criteria_set.id)


def _report(
    session: Session,
    user: User,
    job: Job,
    *,
    mode: str,
    criteria_set_id: uuid.UUID | None,
) -> dict:
    normalized_mode = mode.upper()
    if normalized_mode not in ALLOWED_MODES:
        raise HTTPException(status_code=422, detail="Unsupported Recruiter Lens perspective")
    custom_criteria, set_mode, resolved_set_id = _criteria_for_user(
        session, user, criteria_set_id
    )
    if set_mode is not None:
        normalized_mode = set_mode
    payload = build_recruiter_lens(
        session,
        user,
        job,
        mode=normalized_mode,
        custom_criteria=custom_criteria,
        criteria_set_id=resolved_set_id,
    )
    return {
        **payload,
        "report": {
            "job_id": str(job.id),
            "job_title": job.title,
            "candidate_controlled": True,
            "print_friendly": True,
            "employer_decision": False,
        },
    }


@router.get("/jobs/{job_id}")
def get_recruiter_lens(
    job_id: uuid.UUID,
    mode: str = Query(default="DEFAULT_RECRUITER"),
    criteria_set_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    return _report(
        session,
        user,
        job,
        mode=mode,
        criteria_set_id=criteria_set_id,
    )


@router.post("/jobs/{job_id}/report-shares", status_code=201)
def create_recruiter_lens_report_share(
    job_id: uuid.UUID,
    mode: str = Query(default="DEFAULT_RECRUITER"),
    criteria_set_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    normalized_mode = mode.upper()
    custom_criteria, set_mode, _resolved = _criteria_for_user(session, user, criteria_set_id)
    if normalized_mode not in ALLOWED_MODES:
        raise HTTPException(status_code=422, detail="Unsupported Recruiter Lens perspective")
    if set_mode is not None:
        normalized_mode = set_mode
    # Building before persistence proves the selected perspective is currently valid and
    # evidence-bound. The public view rebuilds from current verified candidate evidence.
    build_recruiter_lens(
        session,
        user,
        job,
        mode=normalized_mode,
        custom_criteria=custom_criteria,
        criteria_set_id=str(criteria_set_id) if criteria_set_id else None,
    )
    row = RecruiterLensReportShare(
        user_id=user.id,
        job_id=job.id,
        criteria_set_id=criteria_set_id,
        public_token=secrets.token_urlsafe(36),
        mode=normalized_mode,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {
        "id": str(row.id),
        "job_id": str(row.job_id),
        "mode": row.mode,
        "criteria_set_id": str(row.criteria_set_id) if row.criteria_set_id else None,
        "public_path": f"/recruiter-report/{row.public_token}",
        "revoked": row.revoked,
        "created_at": row.created_at.isoformat(),
        "privacy": {
            "candidate_controlled": True,
            "named_viewer_tracking": False,
            "employer_decision": False,
        },
    }


@router.get("/report-shares")
def list_recruiter_lens_report_shares(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    rows = session.scalars(
        select(RecruiterLensReportShare)
        .where(RecruiterLensReportShare.user_id == user.id)
        .order_by(RecruiterLensReportShare.created_at.desc())
    ).all()
    return [
        {
            "id": str(row.id),
            "job_id": str(row.job_id),
            "mode": row.mode,
            "criteria_set_id": str(row.criteria_set_id) if row.criteria_set_id else None,
            "public_path": None if row.revoked else f"/recruiter-report/{row.public_token}",
            "revoked": row.revoked,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post("/report-shares/{share_id}/revoke")
def revoke_recruiter_lens_report_share(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.scalar(
        select(RecruiterLensReportShare).where(
            RecruiterLensReportShare.id == share_id,
            RecruiterLensReportShare.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recruiter Lens report share not found")
    row.revoked = True
    session.commit()
    return {"id": str(row.id), "revoked": True}


@router.get("/public/reports/{token}")
def public_recruiter_lens_report(
    token: str,
    session: Session = Depends(get_session),
) -> dict:
    row = session.scalar(
        select(RecruiterLensReportShare).where(
            RecruiterLensReportShare.public_token == token,
            RecruiterLensReportShare.revoked.is_(False),
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recruiter Lens report not found")
    user = session.scalar(select(User).where(User.id == row.user_id))
    job = session.scalar(select(Job).where(Job.id == row.job_id))
    if user is None or job is None:
        raise HTTPException(status_code=404, detail="Recruiter Lens report not found")
    custom_criteria, set_mode, _resolved = _criteria_for_user(
        session, user, row.criteria_set_id
    )
    mode = set_mode or row.mode
    payload = build_recruiter_lens(
        session,
        user,
        job,
        mode=mode,
        custom_criteria=custom_criteria,
        criteria_set_id=str(row.criteria_set_id) if row.criteria_set_id else None,
    )
    return {
        **payload,
        "report": {
            "job_id": str(job.id),
            "job_title": job.title,
            "candidate_controlled": True,
            "print_friendly": True,
            "employer_decision": False,
            "share_id": str(row.id),
        },
        "privacy": {
            "named_viewer_tracking": False,
            "company_identity_inferred": False,
            "hiring_probability": False,
        },
    }
