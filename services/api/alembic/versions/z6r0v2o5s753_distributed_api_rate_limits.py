"""add distributed api rate limit buckets

Revision ID: z6r0v2o5s753
Revises: y5q9u1n4r642
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "z6r0v2o5s753"
down_revision: str | None = "y5q9u1n4r642"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_rate_limit_buckets",
        sa.Column("scope", sa.String(64), primary_key=True),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_api_rate_limit_buckets_expires_at",
        "api_rate_limit_buckets",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_table("api_rate_limit_buckets")
