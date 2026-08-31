"""resume share intelligence

Revision ID: k1c5g7b0d208
Revises: j0b4f6a9c197
Create Date: 2026-08-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "k1c5g7b0d208"
down_revision: str | None = "j0b4f6a9c197"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_share_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pinned_resume_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("public_token", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("channel", sa.String(length=80), nullable=True),
        sa.Column("always_current", sa.Boolean(), nullable=False),
        sa.Column("allow_download", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pinned_resume_version_id"], ["resume_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_token"),
    )
    op.create_index("ix_resume_share_links_user_id", "resume_share_links", ["user_id"], unique=False)
    op.create_index("ix_resume_share_links_resume_id", "resume_share_links", ["resume_id"], unique=False)
    op.create_index("ix_resume_share_links_job_id", "resume_share_links", ["job_id"], unique=False)
    op.create_index("ix_resume_share_links_application_id", "resume_share_links", ["application_id"], unique=False)
    op.create_index("ix_resume_share_links_public_token", "resume_share_links", ["public_token"], unique=True)
    op.create_index(
        "ix_resume_share_links_user_status_created",
        "resume_share_links",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_resume_share_links_job_created", "resume_share_links", ["job_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_resume_share_links_application_created",
        "resume_share_links",
        ["application_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "resume_share_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("share_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_hash", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_value", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suspected_bot", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["share_id"], ["resume_share_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_share_events_share_id", "resume_share_events", ["share_id"], unique=False)
    op.create_index(
        "ix_resume_share_events_share_time",
        "resume_share_events",
        ["share_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_resume_share_events_share_session",
        "resume_share_events",
        ["share_id", "session_hash", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_resume_share_events_share_session", table_name="resume_share_events")
    op.drop_index("ix_resume_share_events_share_time", table_name="resume_share_events")
    op.drop_index("ix_resume_share_events_share_id", table_name="resume_share_events")
    op.drop_table("resume_share_events")

    op.drop_index("ix_resume_share_links_application_created", table_name="resume_share_links")
    op.drop_index("ix_resume_share_links_job_created", table_name="resume_share_links")
    op.drop_index("ix_resume_share_links_user_status_created", table_name="resume_share_links")
    op.drop_index("ix_resume_share_links_public_token", table_name="resume_share_links")
    op.drop_index("ix_resume_share_links_application_id", table_name="resume_share_links")
    op.drop_index("ix_resume_share_links_job_id", table_name="resume_share_links")
    op.drop_index("ix_resume_share_links_resume_id", table_name="resume_share_links")
    op.drop_index("ix_resume_share_links_user_id", table_name="resume_share_links")
    op.drop_table("resume_share_links")
