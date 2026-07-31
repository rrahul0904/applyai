"""career site discovery and queued URL imports

Revision ID: a1e7c9d4f280
Revises: 9d6f2a1c4b70
Create Date: 2026-07-31 20:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1e7c9d4f280"
down_revision: Union[str, None] = "9d6f2a1c4b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_source_discoveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_registry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("input_url", sa.Text(), nullable=False),
        sa.Column("input_domain", sa.String(length=255), nullable=False),
        sa.Column("discovered_careers_url", sa.Text(), nullable=True),
        sa.Column("discovered_url", sa.Text(), nullable=True),
        sa.Column("resolved_url", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("apply_url", sa.Text(), nullable=True),
        sa.Column("detected_provider", sa.String(length=48), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("access_policy", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_category", sa.String(length=48), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_registry_id"], ["job_source_registry.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_key", name="uq_job_source_discoveries_request_key"),
    )
    op.create_index("ix_job_source_discoveries_user_id", "job_source_discoveries", ["user_id"])
    op.create_index("ix_job_source_discoveries_company_id", "job_source_discoveries", ["company_id"])
    op.create_index("ix_job_source_discoveries_source_registry_id", "job_source_discoveries", ["source_registry_id"])
    op.create_index("ix_job_source_discoveries_job_id", "job_source_discoveries", ["job_id"])
    op.create_index(
        "ix_job_source_discoveries_user_created",
        "job_source_discoveries",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_job_source_discoveries_status_created",
        "job_source_discoveries",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_job_source_discoveries_domain",
        "job_source_discoveries",
        ["input_domain", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_source_discoveries_domain", table_name="job_source_discoveries")
    op.drop_index("ix_job_source_discoveries_status_created", table_name="job_source_discoveries")
    op.drop_index("ix_job_source_discoveries_user_created", table_name="job_source_discoveries")
    op.drop_index("ix_job_source_discoveries_job_id", table_name="job_source_discoveries")
    op.drop_index("ix_job_source_discoveries_source_registry_id", table_name="job_source_discoveries")
    op.drop_index("ix_job_source_discoveries_company_id", table_name="job_source_discoveries")
    op.drop_index("ix_job_source_discoveries_user_id", table_name="job_source_discoveries")
    op.drop_table("job_source_discoveries")
