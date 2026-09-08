"""add provider-neutral auth identity and database roles

Revision ID: o5g9k1d4h642
Revises: n4f8j0d3g531
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "o5g9k1d4h642"
down_revision: str | None = "n4f8j0d3g531"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "clerk_user_id", existing_type=sa.String(length=128), nullable=True)
    op.add_column(
        "users",
        sa.Column("auth_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'clerk'"),
        ),
    )
    op.create_index("ix_users_auth_user_id", "users", ["auth_user_id"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    roles = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        roles,
        [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "candidate",
                "description": "Standard candidate workspace access",
            },
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "name": "operator",
                "description": "Operations control-plane access",
            },
            {
                "id": "00000000-0000-0000-0000-000000000003",
                "name": "admin",
                "description": "Administrative control-plane access",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_index("ix_users_auth_user_id", table_name="users")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "auth_user_id")
    op.alter_column("users", "clerk_user_id", existing_type=sa.String(length=128), nullable=False)
