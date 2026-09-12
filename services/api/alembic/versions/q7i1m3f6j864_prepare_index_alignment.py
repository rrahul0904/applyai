"""align ApplyAI Prepare indexes with ORM metadata

Revision ID: q7i1m3f6j864
Revises: p6h0l2e5i753
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "q7i1m3f6j864"
down_revision: str | None = "p6h0l2e5i753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    ("ix_courses_user_id", "courses", ["user_id"]),
    ("ix_courses_job_id", "courses", ["job_id"]),
    ("ix_lesson_conversations_user_id", "lesson_conversations", ["user_id"]),
    ("ix_lesson_conversations_course_lesson_id", "lesson_conversations", ["course_lesson_id"]),
    ("ix_learning_exercises_course_lesson_id", "learning_exercises", ["course_lesson_id"]),
    ("ix_exercise_attempts_user_id", "exercise_attempts", ["user_id"]),
    ("ix_exercise_attempts_learning_exercise_id", "exercise_attempts", ["learning_exercise_id"]),
    ("ix_learning_progress_user_id", "learning_progress", ["user_id"]),
    ("ix_learning_progress_course_lesson_id", "learning_progress", ["course_lesson_id"]),
    ("ix_interview_packs_user_id", "interview_packs", ["user_id"]),
    ("ix_interview_packs_job_id", "interview_packs", ["job_id"]),
    ("ix_mock_interview_sessions_user_id", "mock_interview_sessions", ["user_id"]),
    ("ix_mock_interview_sessions_job_id", "mock_interview_sessions", ["job_id"]),
    ("ix_interview_recordings_interview_session_id", "interview_recordings", ["interview_session_id"]),
    ("ix_candidate_skill_evidence_user_id", "candidate_skill_evidence", ["user_id"]),
    ("ix_candidate_skill_evidence_job_id", "candidate_skill_evidence", ["job_id"]),
    ("ix_career_readiness_snapshots_user_id", "career_readiness_snapshots", ["user_id"]),
    ("ix_career_readiness_snapshots_job_id", "career_readiness_snapshots", ["job_id"]),
    ("ix_usage_ledger_user_id", "usage_ledger", ["user_id"]),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
