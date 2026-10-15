"""Add explicit source coverage receipts for RE-347 Phase A.

Revision ID: b8t2x4q7u975
Revises: a7s1w3p6t864
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8t2x4q7u975"
down_revision: str | None = "a7s1w3p6t864"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_ingestion_runs",
        sa.Column(
            "coverage_status",
            sa.String(16),
            nullable=False,
            server_default="INCONCLUSIVE",
        ),
    )
    op.add_column(
        "job_ingestion_runs",
        sa.Column(
            "coverage_details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("job_ingestion_runs", "coverage_details")
    op.drop_column("job_ingestion_runs", "coverage_status")
