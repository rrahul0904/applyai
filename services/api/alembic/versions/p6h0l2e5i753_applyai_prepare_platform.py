"""add ApplyAI Prepare learning and interview platform

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


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def upgrade() -> None:
    op.create_table(
        "job_skill_gaps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_name", sa.String(160), nullable=False),
        sa.Column("normalized_skill", sa.String(160), nullable=False),
        sa.Column("requirement_level", sa.String(32), nullable=False, server_default="REQUIRED"),
        sa.Column("candidate_level", sa.String(32), nullable=False, server_default="NO_EVIDENCE"),
        sa.Column("gap_severity", sa.String(32), nullable=False, server_default="MEDIUM"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0.8000"),
        sa.Column("job_evidence_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("candidate_evidence_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "job_id", "normalized_skill", name="uq_job_skill_gap_user_job_skill"),
    )
    op.create_index("ix_job_skill_gaps_user_job_priority", "job_skill_gaps", ["user_id", "job_id", "priority"])
    op.create_index("ix_job_skill_gaps_user_id", "job_skill_gaps", ["user_id"])
    op.create_index("ix_job_skill_gaps_job_id", "job_skill_gaps", ["job_id"])

    op.create_table(
        "learning_paths",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strategy_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "job_id", "version", name="uq_learning_path_user_job_version"),
    )
    op.create_index("ix_learning_paths_user_job_status", "learning_paths", ["user_id", "job_id", "status"])
    op.create_index("ix_learning_paths_user_id", "learning_paths", ["user_id"])
    op.create_index("ix_learning_paths_job_id", "learning_paths", ["job_id"])

    op.create_table(
        "learning_path_skills",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("learning_path_id", UUID, sa.ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_skill_gap_id", UUID, sa.ForeignKey("job_skill_gaps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("skill_name", sa.String(160), nullable=False),
        sa.Column("normalized_skill", sa.String(160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("target_level", sa.String(32), nullable=False, server_default="INTERVIEW_READY"),
        sa.Column("status", sa.String(32), nullable=False, server_default="NOT_STARTED"),
        sa.UniqueConstraint("learning_path_id", "normalized_skill", name="uq_learning_path_skill"),
    )
    op.create_index("ix_learning_path_skills_learning_path_id", "learning_path_skills", ["learning_path_id"])
    op.create_index("ix_learning_path_skills_job_skill_gap_id", "learning_path_skills", ["job_skill_gap_id"])

    op.create_table(
        "courses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("learning_path_id", UUID, sa.ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_name", sa.String(160), nullable=False),
        sa.Column("normalized_skill", sa.String(160), nullable=False),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("level", sa.String(32), nullable=False, server_default="INTERMEDIATE"),
        sa.Column("status", sa.String(32), nullable=False, server_default="READY"),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generated_by_run_id", UUID, sa.ForeignKey("ai_job_runs.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("learning_path_id", "normalized_skill", name="uq_course_learning_path_skill"),
    )
    op.create_index("ix_courses_user_job", "courses", ["user_id", "job_id"])
    op.create_index("ix_courses_learning_path_id", "courses", ["learning_path_id"])

    op.create_table(
        "course_modules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("course_id", UUID, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.UniqueConstraint("course_id", "position", name="uq_course_module_position"),
    )
    op.create_index("ix_course_modules_course_id", "course_modules", ["course_id"])

    op.create_table(
        "course_lessons",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("course_module_id", UUID, sa.ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("key_points_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("resources_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.UniqueConstraint("course_module_id", "position", name="uq_course_lesson_position"),
    )
    op.create_index("ix_course_lessons_course_module_id", "course_lessons", ["course_module_id"])

    op.create_table(
        "lesson_conversations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_lesson_id", UUID, sa.ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_lesson_conversations_user_lesson", "lesson_conversations", ["user_id", "course_lesson_id", "created_at"])

    op.create_table(
        "learning_exercises",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("course_lesson_id", UUID, sa.ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_type", sa.String(32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("rubric_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("answer_key_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("difficulty", sa.String(32), nullable=False, server_default="ADAPTIVE"),
    )
    op.create_index("ix_learning_exercises_lesson_type", "learning_exercises", ["course_lesson_id", "exercise_type"])

    op.create_table(
        "exercise_attempts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learning_exercise_id", UUID, sa.ForeignKey("learning_exercises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="SCORED"),
        sa.Column("feedback_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_exercise_attempts_user_exercise", "exercise_attempts", ["user_id", "learning_exercise_id", "created_at"])

    op.create_table(
        "learning_progress",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_lesson_id", UUID, sa.ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mastery_score", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "course_lesson_id", name="uq_learning_progress_user_lesson"),
    )

    op.create_table(
        "interview_packs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("strategy_summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="READY"),
        sa.Column("evidence_refs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("generated_by_run_id", UUID, sa.ForeignKey("ai_job_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "job_id", "version", name="uq_interview_pack_user_job_version"),
    )
    op.create_index("ix_interview_packs_user_job", "interview_packs", ["user_id", "job_id"])

    op.create_table(
        "interview_pack_sections",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("interview_pack_id", UUID, sa.ForeignKey("interview_packs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_type", sa.String(48), nullable=False),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("interview_pack_id", "section_type", name="uq_interview_pack_section_type"),
    )
    op.create_index("ix_interview_pack_sections_interview_pack_id", "interview_pack_sections", ["interview_pack_id"])

    op.create_table(
        "mock_interview_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interview_pack_id", UUID, sa.ForeignKey("interview_packs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default="WRITTEN"),
        sa.Column("difficulty", sa.String(32), nullable=False, server_default="ADAPTIVE"),
        sa.Column("status", sa.String(32), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("provider", sa.String(64), nullable=False, server_default="applyai"),
        sa.Column("provider_session_id", sa.String(255), nullable=True),
        sa.Column("current_question_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("category_scores_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("final_feedback_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_mock_interviews_user_job_created", "mock_interview_sessions", ["user_id", "job_id", "created_at"])

    op.create_table(
        "interview_turns",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("interview_session_id", UUID, sa.ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.String(160), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("follow_up", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("evaluation_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("interview_session_id", "position", name="uq_interview_turn_position"),
    )
    op.create_index("ix_interview_turns_interview_session_id", "interview_turns", ["interview_session_id"])

    op.create_table(
        "interview_recordings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("interview_session_id", UUID, sa.ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.String(16), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False, server_default="browser"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_recordings_session_created", "interview_recordings", ["interview_session_id", "created_at"])

    op.create_table(
        "candidate_skill_evidence",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("normalized_skill", sa.String(160), nullable=False),
        sa.Column("skill_name", sa.String(160), nullable=False),
        sa.Column("evidence_type", sa.String(48), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_candidate_skill_evidence_user_skill", "candidate_skill_evidence", ["user_id", "normalized_skill", "created_at"])

    op.create_table(
        "career_readiness_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("application_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("learning_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interview_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("breakdown_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_readiness_user_job_created", "career_readiness_snapshots", ["user_id", "job_id", "created_at"])

    op.create_table(
        "usage_ledger",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature", sa.String(64), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.Column("related_id", sa.String(255), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_usage_ledger_user_created", "usage_ledger", ["user_id", "created_at"])
    op.create_index("ix_usage_ledger_feature", "usage_ledger", ["feature"])


def downgrade() -> None:
    for table in (
        "usage_ledger", "career_readiness_snapshots", "candidate_skill_evidence",
        "interview_recordings", "interview_turns", "mock_interview_sessions",
        "interview_pack_sections", "interview_packs", "learning_progress",
        "exercise_attempts", "learning_exercises", "lesson_conversations",
        "course_lessons", "course_modules", "courses", "learning_path_skills",
        "learning_paths", "job_skill_gaps",
    ):
        op.drop_table(table)
