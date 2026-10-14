from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.application_agent import (
    BrowserCompletionWrite,
    complete_browser_execution as complete_browser_execution_unchecked,
)
from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.application_agent_models import ApplicationExecution


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
    if body.status in {"SUBMITTED", "CONFIRMED"}:
        verified_ids = body.validation.get("verified_field_ids")
        page_receipts = body.validation.get("verification_pages")
        filled_and_read_back = {
            str(item.get("field_id"))
            for item in body.field_results
            if item.get("status") == "FILLED" and item.get("read_back_verified") is True
        }
        receipt_ids: set[str] = set()
        pages_are_valid = isinstance(page_receipts, list) and bool(page_receipts)
        if pages_are_valid:
            for page in page_receipts:
                checked = page.get("checked") if isinstance(page, dict) else None
                if not isinstance(checked, list) or any(
                    not isinstance(field_id, str) or not field_id for field_id in checked
                ):
                    pages_are_valid = False
                    break
                receipt_ids.update(checked)
        valid_receipt_shape = (
            body.validation.get("pre_submit_verified") is True
            and isinstance(verified_ids, list)
            and bool(verified_ids)
            and all(isinstance(field_id, str) and field_id for field_id in verified_ids)
            and len(set(verified_ids)) == len(verified_ids)
            and pages_are_valid
            and set(verified_ids) == receipt_ids
            and set(verified_ids) <= filled_and_read_back
        )
        if not valid_receipt_shape:
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

        execution = session.scalar(
            select(ApplicationExecution)
            .where(ApplicationExecution.id == execution_id)
            .with_for_update()
        )
        if execution is not None:
            expected_ids = {
                str(field.get("field_id"))
                for field in execution.fields or []
                if field.get("candidate_verified") is True
                and field.get("value") not in (None, "")
                and field.get("canonical_key") != "legal_attestation"
            }
            has_required_attestation = any(
                field.get("required") is True
                and field.get("canonical_key") == "legal_attestation"
                for field in execution.fields or []
            )
            if has_required_attestation or not set(verified_ids) <= expected_ids:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "PRE_SUBMIT_VERIFICATION_REQUIRED",
                        "message": (
                            "Browser submission receipt does not match candidate-approved "
                            "fields or requires a human legal attestation."
                        ),
                    },
                )

    return complete_browser_execution_unchecked(
        execution_id=execution_id,
        body=body,
        session=session,
    )
