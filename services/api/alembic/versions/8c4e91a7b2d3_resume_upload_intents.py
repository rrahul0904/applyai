"""durable resume upload intents

Revision ID: 8c4e91a7b2d3
Revises: 7b9c4d1e2f60
Create Date: 2026-07-29 01:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "8c4e91a7b2d3"
down_revision: Union[str, None] = "7b9c4d1e2f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_upload_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resume_version_id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_resume_upload_intents_resume_id",
        "resume_upload_intents",
        ["resume_id"],
    )
    op.create_index(
        "ix_resume_upload_intents_status",
        "resume_upload_intents",
        ["status"],
    )
    op.create_index(
        "ix_resume_upload_intents_user_id",
        "resume_upload_intents",
        ["user_id"],
    )
    op.create_index(
        "ix_resume_upload_intents_user_status",
        "resume_upload_intents",
        ["user_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_upload_intents_user_status", table_name="resume_upload_intents")
    op.drop_index("ix_resume_upload_intents_user_id", table_name="resume_upload_intents")
    op.drop_index("ix_resume_upload_intents_status", table_name="resume_upload_intents")
    op.drop_index("ix_resume_upload_intents_resume_id", table_name="resume_upload_intents")
    op.drop_table("resume_upload_intents")
