"""durable verified career memory

Revision ID: d4b8f0a2c531
Revises: c3a7e9f1b420
Create Date: 2026-08-06 23:02:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4b8f0a2c531"
down_revision: Union[str, None] = "c3a7e9f1b420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_career_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=48), nullable=False, server_default="USER"),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("provenance", sa.String(length=48), nullable=False, server_default="USER_VERIFIED"),
        sa.Column("user_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("occurred_at", sa.Date(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_career_facts_user_id", "candidate_career_facts", ["user_id"])
    op.create_index(
        "ix_candidate_career_facts_user_category",
        "candidate_career_facts",
        ["user_id", "category"],
    )
    op.create_index(
        "ix_candidate_career_facts_user_verified",
        "candidate_career_facts",
        ["user_id", "user_verified"],
    )


def downgrade() -> None:
    op.drop_table("candidate_career_facts")
