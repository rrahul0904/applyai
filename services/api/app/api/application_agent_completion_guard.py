from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.application_agent import (
    BrowserCompletionWrite,
    complete_browser_execution as complete_browser_execution_unchecked,
)
from app.core.database import get_session
from app.core.internal_auth import require_internal_api


router = APIRouter(
    prefix="/internal/application-agent",
    tags=["internal-application-agent"],
    dependencies=[Depends(require_internal_api)],
)


@router.post("/executions/{execution_id}/complete")
def complete_verified_browser_execution(
    execution_id: uuid.UUID,
    body: BrowserCompletionWrite,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if body.status in {"SUBMITTED", "CONFIRMED"} and body.validation.get("pre_submit_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PRE_SUBMIT_VERIFICATION_REQUIRED",
                "message": (
                    "Browser submission cannot be accepted without a successful "
                    "pre-submit read-back verification receipt."
                ),
            },
        )

    return complete_browser_execution_unchecked(
        execution_id=execution_id,
        body=body,
        session=session,
    )
