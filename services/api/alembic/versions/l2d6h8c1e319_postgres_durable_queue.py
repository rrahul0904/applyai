"""postgres durable queue

Revision ID: l2d6h8c1e319
Revises: k1c5g7b0d208
Create Date: 2026-08-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "l2d6h8c1e319"
down_revision: str | None = "k1c5g7b0d208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "postgres_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("leased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_postgres_tasks_task_type", "postgres_tasks", ["task_type"], unique=False)
    op.create_index("ix_postgres_tasks_status", "postgres_tasks", ["status"], unique=False)
    op.create_index("ix_postgres_tasks_available_at", "postgres_tasks", ["available_at"], unique=False)
    op.create_index("ix_postgres_tasks_idempotency_key", "postgres_tasks", ["idempotency_key"], unique=True)
    op.create_index(
        "ix_postgres_tasks_claim",
        "postgres_tasks",
        ["status", "available_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_postgres_tasks_lease",
        "postgres_tasks",
        ["status", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_postgres_tasks_lease", table_name="postgres_tasks")
    op.drop_index("ix_postgres_tasks_claim", table_name="postgres_tasks")
    op.drop_index("ix_postgres_tasks_idempotency_key", table_name="postgres_tasks")
    op.drop_index("ix_postgres_tasks_available_at", table_name="postgres_tasks")
    op.drop_index("ix_postgres_tasks_status", table_name="postgres_tasks")
    op.drop_index("ix_postgres_tasks_task_type", table_name="postgres_tasks")
    op.drop_table("postgres_tasks")
