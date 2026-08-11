"""application agent v1

Revision ID: j0b4f6a9c197
Revises: i9a3e5f8b086
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "j0b4f6a9c197"
down_revision: str | None = "i9a3e5f8b086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_question_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_key", sa.String(length=120), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=True),
        sa.Column("question_variants", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("answer_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("candidate_verified", sa.Boolean(), nullable=False),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "canonical_key", name="uq_application_question_memory_user_key"),
    )
    op.create_index("ix_application_question_memory_user_id", "application_question_memory", ["user_id"])
    op.create_index(
        "ix_application_question_memory_user_verified",
        "application_question_memory",
        ["user_id", "candidate_verified"],
    )

    op.create_table(
        "application_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_copilot_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("approval_mode", sa.String(length=32), nullable=False),
        sa.Column("ats_provider", sa.String(length=80), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=48), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("review_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("documents", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("browser_handoff", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("confirmation_text", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_copilot_artifact_id"], ["ai_artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "attempt_number", name="uq_application_execution_attempt"),
    )
    op.create_index("ix_application_executions_user_id", "application_executions", ["user_id"])
    op.create_index("ix_application_executions_application_id", "application_executions", ["application_id"])
    op.create_index("ix_application_executions_job_id", "application_executions", ["job_id"])
    op.create_index("ix_application_executions_state", "application_executions", ["state"])
    op.create_index(
        "ix_application_executions_user_state",
        "application_executions",
        ["user_id", "state", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_application_executions_user_state", table_name="application_executions")
    op.drop_index("ix_application_executions_state", table_name="application_executions")
    op.drop_index("ix_application_executions_job_id", table_name="application_executions")
    op.drop_index("ix_application_executions_application_id", table_name="application_executions")
    op.drop_index("ix_application_executions_user_id", table_name="application_executions")
    op.drop_table("application_executions")

    op.drop_index("ix_application_question_memory_user_verified", table_name="application_question_memory")
    op.drop_index("ix_application_question_memory_user_id", table_name="application_question_memory")
    op.drop_table("application_question_memory")
