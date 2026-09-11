from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Role, User, UserRole


_ALLOWED_BOOTSTRAP_ROLES = {"operator", "admin"}


class OperatorBootstrapError(RuntimeError):
    """Raised when an operator bootstrap request is unsafe or cannot be resolved."""


@dataclass(frozen=True)
class OperatorBootstrapResult:
    user_id: str
    email: str
    role: str
    created_assignment: bool


def bootstrap_operator_role(
    session: Session,
    *,
    email: str,
    role_name: str = "operator",
) -> OperatorBootstrapResult:
    """Grant an existing ApplyAI user an operator/admin role.

    The target must already exist as an application user and must already be linked to a
    Supabase Auth identity. This keeps the bootstrap path fail-closed: it cannot create a
    privileged identity, cannot trust user-editable auth metadata, and cannot promote an
    email address that has never successfully authenticated through ApplyAI.
    """

    normalized_email = email.strip().lower()
    normalized_role = role_name.strip().lower()

    if "@" not in normalized_email:
        raise OperatorBootstrapError("A valid operator email is required")
    if normalized_role not in _ALLOWED_BOOTSTRAP_ROLES:
        raise OperatorBootstrapError("Role must be 'operator' or 'admin'")

    users = list(
        session.scalars(
            select(User)
            .where(func.lower(User.email) == normalized_email)
            .limit(2)
        ).all()
    )
    if not users:
        raise OperatorBootstrapError(
            "No ApplyAI user exists for this email. Sign in to production first so the "
            "Supabase identity is verified and linked."
        )
    if len(users) > 1:
        raise OperatorBootstrapError(
            "More than one ApplyAI user matches this email; resolve the identity collision first"
        )

    user = users[0]
    if user.auth_provider != "supabase" or user.auth_user_id is None:
        raise OperatorBootstrapError(
            "The ApplyAI user is not linked to a Supabase Auth identity"
        )
    if user.account_status != "ACTIVE":
        raise OperatorBootstrapError("The target ApplyAI account is not active")

    role = session.scalar(select(Role).where(Role.name == normalized_role))
    if role is None:
        raise OperatorBootstrapError(
            f"Required role '{normalized_role}' is missing; apply database migrations first"
        )

    existing = session.get(UserRole, (user.id, role.id))
    created_assignment = existing is None
    if existing is None:
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()

    return OperatorBootstrapResult(
        user_id=str(user.id),
        email=user.email,
        role=role.name,
        created_assignment=created_assignment,
    )
