from __future__ import annotations

from fastapi import HTTPException
from starlette.requests import Request

from app.core.auth import AuthClaims
from app.core.config import Settings
from app.core.operator_auth import require_operator_or_internal


class StubProvider:
    def __init__(self, email: str) -> None:
        self.email = email

    def authenticate(self, _request: Request) -> AuthClaims:
        return AuthClaims(subject="clerk:test", email=self.email)


def _request(*, bearer: bool = True, internal_token: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if bearer:
        headers.append((b"authorization", b"Bearer test-token"))
    if internal_token:
        headers.append((b"x-applyai-internal-token", internal_token.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_operator_auth_accepts_clerk_operator() -> None:
    settings = Settings(
        operator_emails="operator@example.test",
        internal_api_token="this-is-a-long-enough-internal-token",
    )
    require_operator_or_internal(
        _request(),
        settings=settings,
        provider=StubProvider("OPERATOR@example.test"),
    )


def test_operator_auth_rejects_non_operator() -> None:
    settings = Settings(operator_emails="operator@example.test")
    try:
        require_operator_or_internal(
            _request(),
            settings=settings,
            provider=StubProvider("candidate@example.test"),
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail["code"] == "OPERATOR_FORBIDDEN"
    else:
        raise AssertionError("non-operator should be rejected")


def test_operator_auth_accepts_internal_service_token_without_operator_allowlist() -> None:
    token = "this-is-a-long-enough-internal-token"
    settings = Settings(internal_api_token=token)
    require_operator_or_internal(
        _request(bearer=False, internal_token=token),
        settings=settings,
        provider=StubProvider("candidate@example.test"),
    )


def test_operator_auth_fails_closed_when_not_configured() -> None:
    settings = Settings()
    try:
        require_operator_or_internal(
            _request(),
            settings=settings,
            provider=StubProvider("operator@example.test"),
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail["code"] == "OPERATOR_FORBIDDEN"
    else:
        raise AssertionError("operator auth should fail closed when no allowlist is configured")
