"""add durable worker runtime heartbeat receipts

Revision ID: e1b5c7d9a246
Revises: d0v4z6s9w197
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1b5c7d9a246"
down_revision: str | None = "d0v4z6s9w197"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_runtime_heartbeats",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=48), nullable=False),
        sa.Column("worker_type", sa.String(length=80), nullable=False),
        sa.Column("worker_id", sa.String(length=160), nullable=False),
        sa.Column("deployment_sha", sa.String(length=64), nullable=True),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "environment",
            "worker_type",
            "worker_id",
            name="uq_worker_runtime_heartbeats_instance",
        ),
    )
    op.create_index(
        "ix_worker_runtime_heartbeats_lookup",
        "worker_runtime_heartbeats",
        ["environment", "worker_type", "heartbeat_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_worker_runtime_heartbeats_lookup",
        table_name="worker_runtime_heartbeats",
    )
    op.drop_table("worker_runtime_heartbeats")
