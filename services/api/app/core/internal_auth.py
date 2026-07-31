import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.core.config import Settings, get_settings


def require_internal_api(
    token: Annotated[str | None, Header(alias="X-ApplyAI-Internal-Token")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.internal_api_token
    if not expected or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "INTERNAL_AUTH_REQUIRED",
                "message": "Internal operator authorization is required",
            },
        )
