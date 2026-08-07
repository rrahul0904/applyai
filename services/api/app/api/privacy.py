from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.auth import AuthClaims, get_auth_claims, get_current_user
from app.core.database import Base, get_session
from app.models import User
from app.privacy_models import DeletedIdentity

router = APIRouter(prefix="/account", tags=["privacy"])


def _json_value(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, datetime, date, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


@router.get("/export")
def export_account_data(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    exported: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "account_status": user.account_status,
            "created_at": str(user.created_at),
        },
        "data": {},
    }
    for table in Base.metadata.sorted_tables:
        if table.name in {"users", "deleted_identities"} or "user_id" not in table.c:
            continue
        rows = session.execute(select(table).where(table.c.user_id == user.id)).mappings().all()
        if rows:
            exported["data"][table.name] = [
                {key: _json_value(value) for key, value in row.items()} for row in rows
            ]
    return exported


@router.delete("", status_code=status.HTTP_200_OK)
def delete_account_data(
    claims: AuthClaims = Depends(get_auth_claims),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if user.account_status == "DELETED":
        raise HTTPException(status_code=410, detail="Account data has already been deleted")

    subject_hash = hashlib.sha256(claims.subject.encode("utf-8")).hexdigest()
    if session.scalar(select(DeletedIdentity).where(DeletedIdentity.subject_hash == subject_hash)) is None:
        session.add(DeletedIdentity(subject_hash=subject_hash))
        session.flush()

    # Delete every directly candidate-owned table in reverse dependency order. Tables
    # that reference these rows are removed by their declared ON DELETE CASCADE rules.
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in {"users", "deleted_identities"} or "user_id" not in table.c:
            continue
        session.execute(delete(table).where(table.c.user_id == user.id))

    # Employer jobs and immutable audit records may still reference the user primary key.
    # Keep only an anonymous tombstone row so referential integrity remains valid.
    anonymous_id = uuid.uuid4()
    user.clerk_user_id = f"deleted:{anonymous_id}"
    user.email = f"deleted+{anonymous_id}@invalid.applyai.local"
    user.first_name = None
    user.last_name = None
    user.avatar_url = None
    user.account_status = "DELETED"
    session.commit()
    return {
        "deleted": True,
        "application_data_deleted": True,
        "identity_provider_action_required": "Delete the corresponding Clerk identity in the configured identity provider to revoke the external account itself.",
    }
