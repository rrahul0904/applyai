"""add operations service cost ledger

Revision ID: v2n6r8k1o319
Revises: u1m5q7j0n208
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v2n6r8k1o319"
down_revision: str | None = "u1m5q7j0n208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operations_service_costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_key", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(48), nullable=False, server_default="production"),
        sa.Column("billing_period", sa.String(7), nullable=False),
        sa.Column("fixed_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usage_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("source", sa.String(160), nullable=False, server_default="operator"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "service_key",
            "environment",
            "billing_period",
            name="uq_operations_service_cost_service_env_period",
        ),
    )
    op.create_index(
        "ix_operations_service_cost_period_category",
        "operations_service_costs",
        ["billing_period", "category"],
    )
    op.create_index(
        "ix_operations_service_cost_updated",
        "operations_service_costs",
        ["updated_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("operations_service_costs")
