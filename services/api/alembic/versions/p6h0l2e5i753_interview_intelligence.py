"""add interview intelligence workspace

Revision ID: p6h0l2e5i753
Revises: o5g9k1d4h642
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p6h0l2e5i753"
down_revision: str | None = "o5g9k1d4h642"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "interview_preparations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("job_id", UUID, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="READY"),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("interview_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_phase_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("interviewer_name", sa.String(length=240), nullable=True),
        sa.Column("interviewer_title", sa.String(length=240), nullable=True),
        sa.Column("interviewer_url", sa.Text(), nullable=True),
        sa.Column("company_research", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("role_analysis", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resume_analysis", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("market_benchmark", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("interviewer_brief", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("readiness", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("private_feed_token", sa.String(length=96), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_interview_preparations_user_job"),
        sa.UniqueConstraint("private_feed_token"),
    )
    op.create_index("ix_interview_preparations_user_id", "interview_preparations", ["user_id"], unique=False)
    op.create_index("ix_interview_preparations_job_id", "interview_preparations", ["job_id"], unique=False)
    op.create_index("ix_interview_preparations_private_feed_token", "interview_preparations", ["private_feed_token"], unique=True)
    op.create_index("ix_interview_preparations_user_status", "interview_preparations", ["user_id", "status"], unique=False)

    op.create_table(
        "interview_phases",
        sa.Column("id", UUID, nullable=False),
        sa.Column("preparation_id", UUID, nullable=False),
        sa.Column("phase_number", sa.Integer(), nullable=False),
        sa.Column("phase_type", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UPCOMING"),
        sa.Column("prep", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("quiz", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("flashcards", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reflection", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cheat_sheet", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("readiness", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["preparation_id"], ["interview_preparations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("preparation_id", "phase_number", name="uq_interview_phase_number"),
    )
    op.create_index("ix_interview_phases_preparation_id", "interview_phases", ["preparation_id"], unique=False)
    op.create_index("ix_interview_phases_preparation_status", "interview_phases", ["preparation_id", "status"], unique=False)

    op.create_table(
        "interview_podcast_episodes",
        sa.Column("id", UUID, nullable=False),
        sa.Column("preparation_id", UUID, nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("script", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("duration_estimate_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("audio_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="SCRIPT_READY"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["preparation_id"], ["interview_preparations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("preparation_id", "episode_number", name="uq_interview_episode_number"),
    )
    op.create_index("ix_interview_podcast_episodes_preparation_id", "interview_podcast_episodes", ["preparation_id"], unique=False)

    op.create_table(
        "interview_practice_questions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("phase_id", UUID, nullable=False),
        sa.Column("mode", sa.String(length=48), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("model_answer", sa.Text(), nullable=False),
        sa.Column("rubric", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("followups", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["phase_id"], ["interview_phases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_practice_questions_phase_id", "interview_practice_questions", ["phase_id"], unique=False)
    op.create_index("ix_interview_questions_phase_order", "interview_practice_questions", ["phase_id", "display_order"], unique=False)

    op.create_table(
        "interview_practice_attempts",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("question_id", UUID, nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("transcript_source", sa.String(length=32), nullable=False, server_default="TEXT"),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["question_id"], ["interview_practice_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_practice_attempts_user_id", "interview_practice_attempts", ["user_id"], unique=False)
    op.create_index("ix_interview_practice_attempts_question_id", "interview_practice_attempts", ["question_id"], unique=False)
    op.create_index("ix_interview_attempts_user_question_time", "interview_practice_attempts", ["user_id", "question_id", "created_at"], unique=False)

    op.create_table(
        "interview_research_sources",
        sa.Column("id", UUID, nullable=False),
        sa.Column("preparation_id", UUID, nullable=False),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=320), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("source_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["preparation_id"], ["interview_preparations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_research_sources_preparation_id", "interview_research_sources", ["preparation_id"], unique=False)
    op.create_index("ix_interview_research_preparation_kind", "interview_research_sources", ["preparation_id", "source_kind"], unique=False)

    op.create_table(
        "interview_stories",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("categories", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("task", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("metrics", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skills", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_fact_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_stories_user_id", "interview_stories", ["user_id"], unique=False)
    op.create_index("ix_interview_stories_user_updated", "interview_stories", ["user_id", "updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interview_stories_user_updated", table_name="interview_stories")
    op.drop_index("ix_interview_stories_user_id", table_name="interview_stories")
    op.drop_table("interview_stories")
    op.drop_index("ix_interview_research_preparation_kind", table_name="interview_research_sources")
    op.drop_index("ix_interview_research_sources_preparation_id", table_name="interview_research_sources")
    op.drop_table("interview_research_sources")
    op.drop_index("ix_interview_attempts_user_question_time", table_name="interview_practice_attempts")
    op.drop_index("ix_interview_practice_attempts_question_id", table_name="interview_practice_attempts")
    op.drop_index("ix_interview_practice_attempts_user_id", table_name="interview_practice_attempts")
    op.drop_table("interview_practice_attempts")
    op.drop_index("ix_interview_questions_phase_order", table_name="interview_practice_questions")
    op.drop_index("ix_interview_practice_questions_phase_id", table_name="interview_practice_questions")
    op.drop_table("interview_practice_questions")
    op.drop_index("ix_interview_podcast_episodes_preparation_id", table_name="interview_podcast_episodes")
    op.drop_table("interview_podcast_episodes")
    op.drop_index("ix_interview_phases_preparation_status", table_name="interview_phases")
    op.drop_index("ix_interview_phases_preparation_id", table_name="interview_phases")
    op.drop_table("interview_phases")
    op.drop_index("ix_interview_preparations_user_status", table_name="interview_preparations")
    op.drop_index("ix_interview_preparations_private_feed_token", table_name="interview_preparations")
    op.drop_index("ix_interview_preparations_job_id", table_name="interview_preparations")
    op.drop_index("ix_interview_preparations_user_id", table_name="interview_preparations")
    op.drop_table("interview_preparations")
