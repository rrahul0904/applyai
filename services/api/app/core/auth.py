import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from hmac import compare_digest

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models import User
from app.privacy_models import DeletedIdentity

logger = logging.getLogger("applyai.zero_cost")


@dataclass(frozen=True)
class AuthClaims:
    subject: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None


class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, request: Request) -> AuthClaims:
        raise NotImplementedError


class ClerkAuthProvider(AuthProvider):
    def __init__(
        self,
        *,
        jwks_url: str | None,
        issuer: str | None,
        audience: str | None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.jwks_client = PyJWKClient(jwks_url, cache_keys=True) if jwks_url else None

    def authenticate(self, request: Request) -> AuthClaims:
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AUTH_REQUIRED", "message": "Authentication required"},
            )
        if not self.jwks_client or not self.issuer:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "AUTH_NOT_CONFIGURED",
                    "message": "Clerk authentication is not configured",
                },
            )
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            decode_options: dict[str, object] = {
                "algorithms": ["RS256"],
                "issuer": self.issuer,
                "options": {"require": ["exp", "iat", "nbf", "sub"]},
            }
            if self.audience:
                decode_options["audience"] = self.audience
            else:
                decode_options["options"] = {
                    "require": ["exp", "iat", "nbf", "sub"],
                    "verify_aud": False,
                }
            payload = jwt.decode(token, signing_key.key, **decode_options)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "SESSION_INVALID", "message": "Your session is no longer valid"},
            ) from exc

        email = payload.get("email")
        if not isinstance(email, str) or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "EMAIL_CLAIM_REQUIRED",
                    "message": "The authenticated session is missing an email claim",
                },
            )
        return AuthClaims(
            subject=str(payload["sub"]),
            email=email,
            first_name=payload.get("first_name"),
            last_name=payload.get("last_name"),
            avatar_url=payload.get("image_url"),
        )


class DevTestAuthProvider(AuthProvider):
    def __init__(self, settings: Settings) -> None:
        if settings.app_env.lower() in {"staging", "production"}:
            raise RuntimeError("Development authentication cannot run in staging or production")
        if not settings.dev_auth_enabled or not settings.dev_auth_secret:
            raise RuntimeError("Development authentication requires explicit configuration")
        self.secret = settings.dev_auth_secret

    def authenticate(self, request: Request) -> AuthClaims:
        supplied_secret = request.headers.get("x-applyai-dev-secret", "")
        email = request.headers.get("x-applyai-dev-user", "").strip().lower()
        if not compare_digest(supplied_secret, self.secret) or "@" not in email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "DEV_AUTH_INVALID", "message": "Development sign-in is invalid"},
            )
        local_part = email.split("@", 1)[0]
        display = " ".join(piece.capitalize() for piece in local_part.replace(".", " ").split())
        first_name, _, last_name = display.partition(" ")
        return AuthClaims(
            subject=f"dev:{email}",
            email=email,
            first_name=first_name or "Candidate",
            last_name=last_name or None,
        )


@lru_cache(maxsize=8)
def _cached_clerk_provider(
    jwks_url: str | None, issuer: str | None, audience: str | None
) -> ClerkAuthProvider:
    return ClerkAuthProvider(jwks_url=jwks_url, issuer=issuer, audience=audience)


def get_auth_provider(settings: Settings = Depends(get_settings)) -> AuthProvider:
    if settings.auth_provider == "dev-test":
        return DevTestAuthProvider(settings)
    return _cached_clerk_provider(
        settings.clerk_jwks_url, settings.clerk_issuer, settings.clerk_audience
    )


def get_auth_claims(
    request: Request, provider: AuthProvider = Depends(get_auth_provider)
) -> AuthClaims:
    return provider.authenticate(request)


def get_current_user(
    claims: AuthClaims = Depends(get_auth_claims),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    subject_hash = hashlib.sha256(claims.subject.encode("utf-8")).hexdigest()
    if (
        session.scalar(
            select(DeletedIdentity.id).where(DeletedIdentity.subject_hash == subject_hash)
        )
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "ACCOUNT_DELETED",
                "message": "This ApplyAI account has been permanently deleted",
            },
        )
    user = session.scalar(select(User).where(User.clerk_user_id == claims.subject))
    if user is None:
        user = User(
            clerk_user_id=claims.subject,
            email=claims.email,
            first_name=claims.first_name,
            last_name=claims.last_name,
            avatar_url=claims.avatar_url,
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            user = session.scalar(select(User).where(User.clerk_user_id == claims.subject))
            if user is None:
                raise
        session.refresh(user)
        retained_users = int(session.scalar(select(func.count()).select_from(User)) or 0)
        if retained_users >= settings.clerk_mru_review_threshold:
            logger.error("clerk_mru_business_review", extra={"retained_users": retained_users})
        elif retained_users >= settings.clerk_mru_critical_threshold:
            logger.error("clerk_mru_critical", extra={"retained_users": retained_users})
        elif retained_users >= settings.clerk_mru_warning_threshold:
            logger.warning("clerk_mru_warning", extra={"retained_users": retained_users})
    if user.account_status == "DELETED":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "ACCOUNT_DELETED",
                "message": "This ApplyAI account has been permanently deleted",
            },
        )
    return user
