"""scope interview community posts to questions

Revision ID: y5q9u1n4r642
Revises: x4p8t0m3q531
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "y5q9u1n4r642"
down_revision: str | None = "x4p8t0m3q531"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_community_posts",
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_interview_community_posts_question_id",
        "interview_community_posts",
        "interview_intelligence_questions",
        ["question_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_interview_community_posts_question_id",
        "interview_community_posts",
        ["question_id"],
    )
    op.create_index(
        "ix_interview_community_posts_question_created",
        "interview_community_posts",
        ["question_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_community_posts_question_created", table_name="interview_community_posts")
    op.drop_index("ix_interview_community_posts_question_id", table_name="interview_community_posts")
    op.drop_constraint(
        "fk_interview_community_posts_question_id",
        "interview_community_posts",
        type_="foreignkey",
    )
    op.drop_column("interview_community_posts", "question_id")
