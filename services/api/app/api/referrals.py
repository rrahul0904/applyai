from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.growth_models import ReferralCode, ReferralCreditLedger, ReferralEvent
from app.models import User

router = APIRouter(prefix="/referrals", tags=["referrals"])
internal_router = APIRouter(prefix="/internal/referrals", tags=["internal-referrals"], dependencies=[Depends(require_internal_api)])


class ReferralClaimWrite(BaseModel):
    code: str = Field(min_length=4, max_length=32)


class ReferralQualifyWrite(BaseModel):
    referrer_credit_cents: int = Field(default=1000, ge=0, le=100_000)
    referred_credit_cents: int = Field(default=0, ge=0, le=100_000)


def _ensure_code(session: Session, user: User) -> ReferralCode:
    item = session.scalar(select(ReferralCode).where(ReferralCode.user_id == user.id))
    if item is not None:
        return item
    for _ in range(5):
        token = secrets.token_urlsafe(6).replace("-", "").replace("_", "").upper()[:10]
        item = ReferralCode(user_id=user.id, code=token, enabled=True)
        session.add(item)
        try:
            session.commit(); session.refresh(item); return item
        except IntegrityError:
            session.rollback()
    raise HTTPException(status_code=503, detail="Could not generate referral code")


@router.get("/me")
def my_referrals(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    code = _ensure_code(session, user)
    events = list(session.scalars(select(ReferralEvent).where(ReferralEvent.referrer_user_id == user.id).order_by(ReferralEvent.created_at.desc()).limit(200)))
    credits = list(session.scalars(select(ReferralCreditLedger).where(ReferralCreditLedger.beneficiary_user_id == user.id).order_by(ReferralCreditLedger.created_at.desc()).limit(500)))
    available = sum(item.amount_cents for item in credits if item.status == "AVAILABLE")
    return {
        "code": code.code,
        "enabled": code.enabled,
        "referrals": [{"id": item.id, "status": item.status, "created_at": item.created_at, "qualified_at": item.qualified_at} for item in events],
        "available_credit_cents": available,
        "ledger": [{"id": item.id, "amount_cents": item.amount_cents, "entry_type": item.entry_type, "status": item.status, "created_at": item.created_at, "applied_at": item.applied_at} for item in credits],
    }


@router.post("/claim", status_code=status.HTTP_201_CREATED)
def claim_referral(payload: ReferralClaimWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    existing = session.scalar(select(ReferralEvent).where(ReferralEvent.referred_user_id == user.id))
    if existing is not None:
        return {"id": existing.id, "status": existing.status, "already_claimed": True}
    code = session.scalar(select(ReferralCode).where(func.upper(ReferralCode.code) == payload.code.strip().upper(), ReferralCode.enabled.is_(True)))
    if code is None:
        raise HTTPException(status_code=404, detail="Referral code not found")
    if code.user_id == user.id:
        raise HTTPException(status_code=409, detail="You cannot claim your own referral code")
    item = ReferralEvent(referral_code_id=code.id, referrer_user_id=code.user_id, referred_user_id=user.id, status="PENDING")
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback(); raise HTTPException(status_code=409, detail="Referral has already been claimed") from exc
    session.refresh(item)
    return {"id": item.id, "status": item.status, "already_claimed": False}


@internal_router.get("/metrics")
def referral_metrics(session: Session = Depends(get_session)) -> dict[str, int]:
    return {
        "codes": int(session.scalar(select(func.count()).select_from(ReferralCode)) or 0),
        "events": int(session.scalar(select(func.count()).select_from(ReferralEvent)) or 0),
        "qualified": int(session.scalar(select(func.count()).select_from(ReferralEvent).where(ReferralEvent.status.in_(["QUALIFIED", "CREDITED"]))) or 0),
        "available_credit_cents": int(session.scalar(select(func.coalesce(func.sum(ReferralCreditLedger.amount_cents), 0)).where(ReferralCreditLedger.status == "AVAILABLE")) or 0),
    }


@internal_router.post("/{event_id}/qualify")
def qualify_referral(event_id: uuid.UUID, payload: ReferralQualifyWrite, session: Session = Depends(get_session)) -> dict[str, Any]:
    event = session.get(ReferralEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Referral event not found")
    if event.status == "PENDING":
        event.status = "QUALIFIED"; event.qualified_at = datetime.now(timezone.utc)
    entries: list[ReferralCreditLedger] = []
    if payload.referrer_credit_cents:
        entries.append(ReferralCreditLedger(referral_event_id=event.id, beneficiary_user_id=event.referrer_user_id, entry_type="REFERRER_CREDIT", amount_cents=payload.referrer_credit_cents, status="AVAILABLE"))
    if payload.referred_credit_cents:
        entries.append(ReferralCreditLedger(referral_event_id=event.id, beneficiary_user_id=event.referred_user_id, entry_type="REFERRED_CREDIT", amount_cents=payload.referred_credit_cents, status="AVAILABLE"))
    for entry in entries:
        exists = session.scalar(select(ReferralCreditLedger).where(ReferralCreditLedger.referral_event_id == event.id, ReferralCreditLedger.beneficiary_user_id == entry.beneficiary_user_id, ReferralCreditLedger.entry_type == entry.entry_type))
        if exists is None: session.add(entry)
    event.status = "CREDITED"
    session.commit()
    return {"id": event.id, "status": event.status, "qualified_at": event.qualified_at}
