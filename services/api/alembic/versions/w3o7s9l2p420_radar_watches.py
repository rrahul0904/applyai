"""add radar watches and bucket transition history

Revision ID: w3o7s9l2p420
Revises: v2n6r8k1o319
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "w3o7s9l2p420"
down_revision: str | None = "v2n6r8k1o319"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "radar_watches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("lookback_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("max_jobs", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_status", sa.String(32)),
        sa.Column("last_scheduled_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_radar_watches_user_id", "radar_watches", ["user_id"])
    op.create_index("ix_radar_watches_next_run_at", "radar_watches", ["next_run_at"])
    op.create_index("ix_radar_watches_due", "radar_watches", ["enabled", "next_run_at", "id"])
    op.create_index("ix_radar_watches_user_created", "radar_watches", ["user_id", "created_at"])

    op.create_table(
        "radar_bucket_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("career_matches.id", ondelete="SET NULL")),
        sa.Column("model_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_job_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engine_version", sa.String(80), nullable=False),
        sa.Column("from_bucket", sa.String(32), nullable=False),
        sa.Column("to_bucket", sa.String(32), nullable=False),
        sa.Column("from_decision", sa.String(32)),
        sa.Column("to_decision", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "job_id", "engine_version", "model_run_id", name="uq_radar_bucket_transition_run"),
    )
    op.create_index("ix_radar_bucket_transitions_user_id", "radar_bucket_transitions", ["user_id"])
    op.create_index("ix_radar_bucket_transitions_job_id", "radar_bucket_transitions", ["job_id"])
    op.create_index("ix_radar_bucket_transitions_model_run_id", "radar_bucket_transitions", ["model_run_id"])
    op.create_index("ix_radar_bucket_transitions_user_created", "radar_bucket_transitions", ["user_id", "created_at", "id"])
    op.create_index("ix_radar_bucket_transitions_job_created", "radar_bucket_transitions", ["job_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("radar_bucket_transitions")
    op.drop_table("radar_watches")
