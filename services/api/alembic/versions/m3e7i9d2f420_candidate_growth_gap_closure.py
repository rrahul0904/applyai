"""candidate growth gap closure

Revision ID: m3e7i9d2f420
Revises: l2d6h8c1e319
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "m3e7i9d2f420"
down_revision: str | None = "l2d6h8c1e319"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_portfolios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("theme", sa.String(length=32), nullable=False),
        sa.Column("indexing_allowed", sa.Boolean(), nullable=False),
        sa.Column("headline", sa.String(length=240), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("visibility_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contact_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_candidate_portfolios_user_id", "candidate_portfolios", ["user_id"], unique=False)
    op.create_index("ix_candidate_portfolios_public", "candidate_portfolios", ["published", "slug"], unique=False)

    op.create_table(
        "candidate_portfolio_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=240), nullable=True),
        sa.Column("technologies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verified_outcome", sa.Text(), nullable=True),
        sa.Column("project_url", sa.Text(), nullable=True),
        sa.Column("repository_url", sa.Text(), nullable=True),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("project_date", sa.Date(), nullable=True),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_portfolio_projects_user_id", "candidate_portfolio_projects", ["user_id"], unique=False)
    op.create_index("ix_candidate_portfolio_projects_user_date", "candidate_portfolio_projects", ["user_id", "project_date"], unique=False)

    op.create_table(
        "recruiter_lens_criteria_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("criteria_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_index("ix_recruiter_lens_criteria_sets_user_id", "recruiter_lens_criteria_sets", ["user_id"], unique=False)
    op.create_index("ix_recruiter_lens_criteria_sets_user_archived", "recruiter_lens_criteria_sets", ["user_id", "archived"], unique=False)

    op.create_table(
        "interview_practice_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("self_review_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_practice_attempts_user_id", "interview_practice_attempts", ["user_id"], unique=False)
    op.create_index("ix_interview_practice_attempts_job_id", "interview_practice_attempts", ["job_id"], unique=False)
    op.create_index("ix_interview_practice_user_job_created", "interview_practice_attempts", ["user_id", "job_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interview_practice_user_job_created", table_name="interview_practice_attempts")
    op.drop_index("ix_interview_practice_attempts_job_id", table_name="interview_practice_attempts")
    op.drop_index("ix_interview_practice_attempts_user_id", table_name="interview_practice_attempts")
    op.drop_table("interview_practice_attempts")
    op.drop_index("ix_recruiter_lens_criteria_sets_user_archived", table_name="recruiter_lens_criteria_sets")
    op.drop_index("ix_recruiter_lens_criteria_sets_user_id", table_name="recruiter_lens_criteria_sets")
    op.drop_table("recruiter_lens_criteria_sets")
    op.drop_index("ix_candidate_portfolio_projects_user_date", table_name="candidate_portfolio_projects")
    op.drop_index("ix_candidate_portfolio_projects_user_id", table_name="candidate_portfolio_projects")
    op.drop_table("candidate_portfolio_projects")
    op.drop_index("ix_candidate_portfolios_public", table_name="candidate_portfolios")
    op.drop_index("ix_candidate_portfolios_user_id", table_name="candidate_portfolios")
    op.drop_table("candidate_portfolios")
