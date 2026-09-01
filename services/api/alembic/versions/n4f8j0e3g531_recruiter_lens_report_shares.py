"""recruiter lens report shares

Revision ID: n4f8j0e3g531
Revises: m3e7i9d2f420
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "n4f8j0e3g531"
down_revision: str | None = "m3e7i9d2f420"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recruiter_lens_report_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("criteria_set_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("public_token", sa.String(length=96), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["criteria_set_id"], ["recruiter_lens_criteria_sets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_token"),
    )
    op.create_index("ix_recruiter_lens_report_shares_user_id", "recruiter_lens_report_shares", ["user_id"], unique=False)
    op.create_index("ix_recruiter_lens_report_shares_job_id", "recruiter_lens_report_shares", ["job_id"], unique=False)
    op.create_index("ix_recruiter_lens_report_shares_user_created", "recruiter_lens_report_shares", ["user_id", "created_at"], unique=False)
    op.create_index("ix_recruiter_lens_report_shares_active_token", "recruiter_lens_report_shares", ["revoked", "public_token"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recruiter_lens_report_shares_active_token", table_name="recruiter_lens_report_shares")
    op.drop_index("ix_recruiter_lens_report_shares_user_created", table_name="recruiter_lens_report_shares")
    op.drop_index("ix_recruiter_lens_report_shares_job_id", table_name="recruiter_lens_report_shares")
    op.drop_index("ix_recruiter_lens_report_shares_user_id", table_name="recruiter_lens_report_shares")
    op.drop_table("recruiter_lens_report_shares")
