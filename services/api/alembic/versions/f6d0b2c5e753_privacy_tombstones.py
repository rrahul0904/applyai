"""privacy tombstones

Revision ID: f6d0b2c5e753
Revises: e5c9a1b4d642
Create Date: 2026-08-07 00:18:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6d0b2c5e753"
down_revision: Union[str, None] = "e5c9a1b4d642"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deleted_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("deleted_identities")
