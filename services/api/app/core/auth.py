import hashlib
import logging
import uuid
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
    provider: str = "clerk"


class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, request: Request) -> AuthClaims:
        raise NotImplementedError


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required"},
        )
    return token


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
        token = _bearer_token(request)
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
            provider="clerk",
        )


class SupabaseAuthProvider(AuthProvider):
    """Verify Supabase Auth access tokens against the project's public JWKS."""

    def __init__(
        self,
        *,
        jwks_url: str | None,
        issuer: str | None,
        audience: str | None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience or "authenticated"
        self.jwks_client = PyJWKClient(jwks_url, cache_keys=True) if jwks_url else None

    def authenticate(self, request: Request) -> AuthClaims:
        token = _bearer_token(request)
        if not self.jwks_client or not self.issuer:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "AUTH_NOT_CONFIGURED",
                    "message": "Supabase authentication is not configured",
                },
            )
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm not in {"ES256", "RS256"}:
                raise ValueError("Unsupported Supabase JWT signing algorithm")
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[algorithm],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "sub", "aud"]},
            )
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
        metadata = payload.get("user_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        full_name = metadata.get("full_name")
        first_name = metadata.get("first_name")
        last_name = metadata.get("last_name")
        if isinstance(full_name, str) and full_name.strip() and not first_name:
            first_name, _, inferred_last = full_name.strip().partition(" ")
            last_name = last_name or inferred_last or None

        return AuthClaims(
            subject=str(payload["sub"]),
            email=email,
            first_name=first_name if isinstance(first_name, str) else None,
            last_name=last_name if isinstance(last_name, str) else None,
            avatar_url=metadata.get("avatar_url") if isinstance(metadata.get("avatar_url"), str) else None,
            provider="supabase",
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
            provider="dev-test",
        )


@lru_cache(maxsize=8)
def _cached_clerk_provider(
    jwks_url: str | None, issuer: str | None, audience: str | None
) -> ClerkAuthProvider:
    return ClerkAuthProvider(jwks_url=jwks_url, issuer=issuer, audience=audience)


@lru_cache(maxsize=8)
def _cached_supabase_provider(
    jwks_url: str | None, issuer: str | None, audience: str | None
) -> SupabaseAuthProvider:
    return SupabaseAuthProvider(jwks_url=jwks_url, issuer=issuer, audience=audience)


def get_auth_provider(settings: Settings = Depends(get_settings)) -> AuthProvider:
    if settings.auth_provider == "dev-test":
        return DevTestAuthProvider(settings)
    if settings.auth_provider == "supabase":
        return _cached_supabase_provider(
            settings.resolved_supabase_jwks_url,
            settings.resolved_supabase_issuer,
            settings.supabase_audience,
        )
    return _cached_clerk_provider(
        settings.clerk_jwks_url, settings.clerk_issuer, settings.clerk_audience
    )


def get_auth_claims(
    request: Request, provider: AuthProvider = Depends(get_auth_provider)
) -> AuthClaims:
    return provider.authenticate(request)


def _find_user_for_claims(session: Session, claims: AuthClaims) -> User | None:
    if claims.provider == "supabase":
        try:
            auth_user_id = uuid.UUID(claims.subject)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "SESSION_INVALID", "message": "Your session is no longer valid"},
            ) from exc
        return session.scalar(select(User).where(User.auth_user_id == auth_user_id))
    return session.scalar(select(User).where(User.clerk_user_id == claims.subject))


def _link_existing_user_by_email(
    session: Session, claims: AuthClaims, auth_user_id: uuid.UUID
) -> User | None:
    matches = list(
        session.scalars(
            select(User)
            .where(func.lower(User.email) == claims.email.strip().lower())
            .limit(2)
        ).all()
    )
    if len(matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "IDENTITY_LINK_REQUIRED",
                "message": "This email maps to more than one ApplyAI account",
            },
        )
    if not matches:
        return None
    user = matches[0]
    if user.auth_user_id is not None and user.auth_user_id != auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "IDENTITY_ALREADY_LINKED",
                "message": "This ApplyAI account is linked to another identity",
            },
        )
    user.auth_user_id = auth_user_id
    user.auth_provider = "supabase"
    session.commit()
    session.refresh(user)
    return user


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

    user = _find_user_for_claims(session, claims)
    if user is None and claims.provider == "supabase":
        auth_user_id = uuid.UUID(claims.subject)
        user = _link_existing_user_by_email(session, claims, auth_user_id)

    if user is None:
        user = User(
            clerk_user_id=claims.subject if claims.provider != "supabase" else None,
            auth_user_id=uuid.UUID(claims.subject) if claims.provider == "supabase" else None,
            auth_provider=claims.provider,
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
            user = _find_user_for_claims(session, claims)
            if user is None:
                raise
        session.refresh(user)

        if claims.provider == "clerk":
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
