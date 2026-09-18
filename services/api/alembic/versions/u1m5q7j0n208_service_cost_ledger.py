"""add platform service cost ledger

Revision ID: u1m5q7j0n208
Revises: t0l4p6i9m197
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u1m5q7j0n208"
down_revision: str | None = "t0l4p6i9m197"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_cost_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("service", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("cost_type", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("amount_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_ref", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_service_cost_entries_idempotency_key", "service_cost_entries", ["idempotency_key"], unique=True)
    op.create_index("ix_service_cost_entries_provider", "service_cost_entries", ["provider"], unique=False)
    op.create_index("ix_service_cost_entries_category", "service_cost_entries", ["category"], unique=False)
    op.create_index("ix_service_cost_entries_period", "service_cost_entries", ["period_end", "period_start"], unique=False)
    op.create_index(
        "ix_service_cost_entries_provider_period",
        "service_cost_entries",
        ["provider", "period_end"],
        unique=False,
    )
    op.create_index(
        "ix_service_cost_entries_category_period",
        "service_cost_entries",
        ["category", "period_end"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_service_cost_entries_category_period", table_name="service_cost_entries")
    op.drop_index("ix_service_cost_entries_provider_period", table_name="service_cost_entries")
    op.drop_index("ix_service_cost_entries_period", table_name="service_cost_entries")
    op.drop_index("ix_service_cost_entries_category", table_name="service_cost_entries")
    op.drop_index("ix_service_cost_entries_provider", table_name="service_cost_entries")
    op.drop_index("ix_service_cost_entries_idempotency_key", table_name="service_cost_entries")
    op.drop_table("service_cost_entries")
