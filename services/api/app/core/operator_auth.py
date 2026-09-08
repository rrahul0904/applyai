from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request, status

from app.core.auth import AuthProvider, get_auth_provider
from app.core.config import Settings, get_settings


def require_operator_or_internal(
    request: Request,
    settings: Settings = Depends(get_settings),
    provider: AuthProvider = Depends(get_auth_provider),
) -> None:
    """Authorize either a trusted service token or an authenticated operator.

    The service token remains available for automation and internal workers. Browser/operator
    traffic should use the candidate's Clerk bearer token and is checked against the API-side
    allowlist, keeping INTERNAL_API_TOKEN out of the web deployment.
    """

    supplied_internal = request.headers.get("x-applyai-internal-token", "")
    expected_internal = settings.internal_api_token
    if (
        expected_internal
        and supplied_internal
        and secrets.compare_digest(supplied_internal, expected_internal)
    ):
        return

    allowed = settings.allowed_operator_emails
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "OPERATOR_AUTH_NOT_CONFIGURED",
                "message": "Operator authorization is not configured",
            },
        )

    claims = provider.authenticate(request)
    if claims.email.strip().lower() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "OPERATOR_FORBIDDEN",
                "message": "Operator authorization is required",
            },
        )
