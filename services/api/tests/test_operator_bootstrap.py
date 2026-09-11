from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.operator_bootstrap import OperatorBootstrapError, bootstrap_operator_role
from app.models import Role, User, UserRole


def _session(database_url: str) -> Session:
    engine = create_engine(database_url)
    return Session(engine)


def test_bootstrap_requires_existing_supabase_linked_user(database_url: str) -> None:
    with _session(database_url) as session:
        session.add(
            Role(
                id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                name="operator",
            )
        )
        session.commit()

        with pytest.raises(OperatorBootstrapError, match="Sign in to production first"):
            bootstrap_operator_role(
                session,
                email="operator@example.test",
                role_name="operator",
            )


def test_bootstrap_rejects_unlinked_identity(database_url: str) -> None:
    with _session(database_url) as session:
        session.add_all(
            [
                Role(
                    id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                    name="operator",
                ),
                User(
                    email="operator@example.test",
                    auth_provider="clerk",
                    clerk_user_id="clerk_test_operator",
                ),
            ]
        )
        session.commit()

        with pytest.raises(OperatorBootstrapError, match="not linked to a Supabase Auth identity"):
            bootstrap_operator_role(
                session,
                email="operator@example.test",
                role_name="operator",
            )


def test_bootstrap_assigns_operator_idempotently(database_url: str) -> None:
    auth_user_id = uuid.uuid4()
    with _session(database_url) as session:
        role = Role(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            name="operator",
        )
        user = User(
            email="Operator@Example.Test",
            auth_provider="supabase",
            auth_user_id=auth_user_id,
        )
        session.add_all([role, user])
        session.commit()

        first = bootstrap_operator_role(
            session,
            email="operator@example.test",
            role_name="operator",
        )
        second = bootstrap_operator_role(
            session,
            email="OPERATOR@example.test",
            role_name="operator",
        )

        assert first.created_assignment is True
        assert second.created_assignment is False
        assignments = list(
            session.scalars(select(UserRole).where(UserRole.user_id == user.id)).all()
        )
        assert len(assignments) == 1
        assert assignments[0].role_id == role.id


def test_bootstrap_rejects_candidate_role(database_url: str) -> None:
    with _session(database_url) as session:
        with pytest.raises(OperatorBootstrapError, match="operator.*admin"):
            bootstrap_operator_role(
                session,
                email="operator@example.test",
                role_name="candidate",
            )
