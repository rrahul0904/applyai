from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models import User
from app.platform_models import BillingLedgerEvent, Subscription

router = APIRouter(prefix="/billing", tags=["billing"])

PLAN_ENTITLEMENTS = {
    "FREE": {"ai_runs_monthly": 20, "resume_variants": 3, "saved_searches": 5, "job_alerts": True, "interview_practice": 5},
    "PRO": {"ai_runs_monthly": 500, "resume_variants": 100, "saved_searches": 100, "job_alerts": True, "interview_practice": 100},
    "TEAM": {"ai_runs_monthly": 2000, "resume_variants": 500, "saved_searches": 500, "job_alerts": True, "interview_practice": 500},
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def billing_provider() -> str:
    return os.getenv("BILLING_PROVIDER", "internal").strip().lower()


def _subscription(session: Session, user: User) -> Subscription:
    item = session.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if item is None:
        item = Subscription(user_id=user.id, plan="FREE", status="ACTIVE", provider="INTERNAL", usage={})
        session.add(item); session.commit(); session.refresh(item)
    return item


class CheckoutWrite(BaseModel):
    plan: Literal["PRO", "TEAM"] = "PRO"


@router.get("/subscription")
def get_subscription(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = _subscription(session, user)
    return {"id": item.id, "plan": item.plan, "status": item.status, "provider": item.provider, "current_period_end": item.current_period_end, "usage": item.usage, "entitlements": PLAN_ENTITLEMENTS.get(item.plan, PLAN_ENTITLEMENTS["FREE"])}


@router.get("/entitlements")
def get_entitlements(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = _subscription(session, user)
    return {"plan": item.plan, "status": item.status, **PLAN_ENTITLEMENTS.get(item.plan, PLAN_ENTITLEMENTS["FREE"]), "usage": item.usage}


@router.post("/checkout")
def create_checkout(payload: CheckoutWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    provider = billing_provider()
    if provider != "stripe":
        raise HTTPException(status_code=503, detail="Billing checkout provider is not configured")
    secret = os.getenv("STRIPE_SECRET_KEY")
    price = os.getenv("STRIPE_PRICE_PRO" if payload.plan == "PRO" else "STRIPE_PRICE_TEAM")
    if not secret or not price:
        raise HTTPException(status_code=503, detail="Stripe checkout configuration is incomplete")
    settings = get_settings()
    data = {
        "mode": "subscription",
        "success_url": f"{settings.web_origin}/settings?billing=success",
        "cancel_url": f"{settings.web_origin}/settings?billing=cancelled",
        "line_items[0][price]": price,
        "line_items[0][quantity]": "1",
        "client_reference_id": str(user.id),
        "customer_email": user.email,
        "metadata[user_id]": str(user.id),
        "metadata[plan]": payload.plan,
        "subscription_data[metadata][user_id]": str(user.id),
        "subscription_data[metadata][plan]": payload.plan,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post("https://api.stripe.com/v1/checkout/sessions", headers={"Authorization": f"Bearer {secret}"}, data=data)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Billing provider is unavailable") from exc
    body = response.json()
    return {"provider": "stripe", "checkout_url": body.get("url"), "checkout_session_id": body.get("id")}


@router.post("/portal")
def create_portal(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = _subscription(session, user)
    if billing_provider() != "stripe" or not item.provider_customer_id:
        raise HTTPException(status_code=409, detail="No managed billing account is available")
    secret = os.getenv("STRIPE_SECRET_KEY")
    if not secret: raise HTTPException(status_code=503, detail="Stripe configuration is incomplete")
    settings = get_settings()
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post("https://api.stripe.com/v1/billing_portal/sessions", headers={"Authorization": f"Bearer {secret}"}, data={"customer": item.provider_customer_id, "return_url": f"{settings.web_origin}/settings"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Billing provider is unavailable") from exc
    return {"portal_url": response.json().get("url")}


def _verify_stripe_signature(raw: bytes, signature: str, secret: str, tolerance: int = 300) -> None:
    parts: dict[str, list[str]] = {}
    for chunk in signature.split(","):
        if "=" in chunk:
            key, value = chunk.split("=", 1); parts.setdefault(key, []).append(value)
    try: timestamp = int(parts.get("t", [""])[0])
    except ValueError as exc: raise HTTPException(status_code=400, detail="Invalid Stripe signature timestamp") from exc
    if abs(int(time.time()) - timestamp) > tolerance: raise HTTPException(status_code=400, detail="Expired Stripe signature")
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", [])):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"), session: Session = Depends(get_session)) -> dict[str, bool]:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if billing_provider() != "stripe" or not secret: raise HTTPException(status_code=503, detail="Stripe webhook is not configured")
    if not stripe_signature: raise HTTPException(status_code=400, detail="Missing Stripe signature")
    raw = await request.body(); _verify_stripe_signature(raw, stripe_signature, secret)
    try: event = json.loads(raw)
    except json.JSONDecodeError as exc: raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc
    event_type = str(event.get("type", "")); obj = event.get("data", {}).get("object", {}) or {}
    metadata = obj.get("metadata", {}) or {}
    user_id_raw = metadata.get("user_id") or obj.get("client_reference_id")
    if not user_id_raw: return {"accepted": True}
    try: user_id = uuid.UUID(str(user_id_raw))
    except ValueError: return {"accepted": True}
    user = session.get(User, user_id)
    if user is None: return {"accepted": True}
    sub = _subscription(session, user)
    if event_type == "checkout.session.completed":
        sub.plan = str(metadata.get("plan") or "PRO"); sub.status = "ACTIVE"; sub.provider = "STRIPE"; sub.provider_customer_id = obj.get("customer"); sub.provider_subscription_id = obj.get("subscription")
    elif event_type in {"customer.subscription.updated", "customer.subscription.created"}:
        sub.plan = str(metadata.get("plan") or sub.plan); sub.status = str(obj.get("status") or "ACTIVE").upper(); sub.provider = "STRIPE"; sub.provider_customer_id = obj.get("customer") or sub.provider_customer_id; sub.provider_subscription_id = obj.get("id") or sub.provider_subscription_id
        if obj.get("current_period_end"): sub.current_period_end = datetime.fromtimestamp(int(obj["current_period_end"]), tz=timezone.utc)
    elif event_type == "customer.subscription.deleted":
        sub.plan = "FREE"; sub.status = "CANCELLED"; sub.provider = "STRIPE"
    session.add(BillingLedgerEvent(user_id=user.id, event_type=event_type, provider_ref=str(event.get("id") or ""), metadata_json={"plan": sub.plan, "status": sub.status}))
    session.commit()
    return {"accepted": True}
