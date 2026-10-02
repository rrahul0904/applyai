"""Persist enqueue-time Job Radar scoring inputs.

Revision ID: d0v4z6s9w197
Revises: c9u3y5r8v086

Legacy rows intentionally remain NULL: the original scoring inputs cannot be
reconstructed from the current mutable profile. Completed results are retained;
legacy pending scans require a fresh scan instead of fabricated historical data.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d0v4z6s9w197"
down_revision = "c9u3y5r8v086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_scans", sa.Column("scoring_profile_snapshot", postgresql.JSONB(), nullable=True))
    op.create_index("ix_jobs_active_recent", "jobs", ["status", sa.text("posted_at DESC NULLS LAST"), sa.text("last_seen_at DESC"), "id"], postgresql_where=sa.text("status = 'ACTIVE'"))


def downgrade() -> None:
    op.drop_index("ix_jobs_active_recent", table_name="jobs")
    op.drop_column("job_scans", "scoring_profile_snapshot")
