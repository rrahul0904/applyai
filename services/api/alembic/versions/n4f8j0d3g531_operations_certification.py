"""persist operations certification evidence

Revision ID: n4f8j0d3g531
Revises: m3e7i9c2f420
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "n4f8j0d3g531"
down_revision: str | None = "m3e7i9c2f420"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operations_certifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("certification_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "environment",
            sa.String(length=48),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("git_sha", sa.String(length=64), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operations_certifications_certification_type",
        "operations_certifications",
        ["certification_type"],
        unique=False,
    )
    op.create_index(
        "ix_operations_certifications_status",
        "operations_certifications",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_operations_certifications_created",
        "operations_certifications",
        ["created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_operations_certifications_status_created",
        "operations_certifications",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operations_certifications_status_created",
        table_name="operations_certifications",
    )
    op.drop_index(
        "ix_operations_certifications_created",
        table_name="operations_certifications",
    )
    op.drop_index(
        "ix_operations_certifications_status",
        table_name="operations_certifications",
    )
    op.drop_index(
        "ix_operations_certifications_certification_type",
        table_name="operations_certifications",
    )
    op.drop_table("operations_certifications")
