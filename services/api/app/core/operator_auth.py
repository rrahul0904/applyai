from __future__ import annotations

import secrets
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthProvider, get_auth_provider
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models import Role, User, UserRole


def _user_for_claims(session: Session, *, provider: str, subject: str) -> User | None:
    if provider == "supabase":
        try:
            auth_user_id = uuid.UUID(subject)
        except ValueError:
            return None
        return session.scalar(select(User).where(User.auth_user_id == auth_user_id))
    return session.scalar(select(User).where(User.clerk_user_id == subject))


def _has_operator_role(session: Session, user_id: uuid.UUID) -> bool:
    return (
        session.scalar(
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.user_id == user_id,
                Role.name.in_(("operator", "admin")),
            )
            .limit(1)
        )
        is not None
    )


def require_operator_or_internal(
    request: Request,
    settings: Settings = Depends(get_settings),
    provider: AuthProvider = Depends(get_auth_provider),
    session: Session = Depends(get_session),
) -> None:
    """Authorize a backend service token or an authenticated database-role operator."""

    supplied_internal = request.headers.get("x-applyai-internal-token", "")
    expected_internal = settings.internal_api_token
    if (
        expected_internal
        and supplied_internal
        and secrets.compare_digest(supplied_internal, expected_internal)
    ):
        return

    claims = provider.authenticate(request)
    user = _user_for_claims(
        session,
        provider=claims.provider,
        subject=claims.subject,
    )
    if user is not None and _has_operator_role(session, user.id):
        return

    # Temporary migration bridge for existing Clerk production only. Supabase authorization
    # deliberately never trusts an environment-variable email allowlist.
    if claims.provider != "supabase" and claims.email.strip().lower() in settings.allowed_operator_emails:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "OPERATOR_FORBIDDEN",
            "message": "Operator authorization is required",
        },
    )
