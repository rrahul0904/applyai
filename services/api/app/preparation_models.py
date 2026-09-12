from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JobSkillGap(Base):
    __tablename__ = "job_skill_gaps"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "normalized_skill", name="uq_job_skill_gap_user_job_skill"),
        Index("ix_job_skill_gaps_user_job_priority", "user_id", "job_id", "priority"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_skill: Mapped[str] = mapped_column(String(160), nullable=False)
    requirement_level: Mapped[str] = mapped_column(String(32), nullable=False, default="REQUIRED")
    candidate_level: Mapped[str] = mapped_column(String(32), nullable=False, default="NO_EVIDENCE")
    gap_severity: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.80"))
    job_evidence_json: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    candidate_evidence_json: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class LearningPath(Base):
    __tablename__ = "learning_paths"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "version", name="uq_learning_path_user_job_version"),
        Index("ix_learning_paths_user_job_status", "user_id", "job_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    strategy_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class LearningPathSkill(Base):
    __tablename__ = "learning_path_skills"
    __table_args__ = (UniqueConstraint("learning_path_id", "normalized_skill", name="uq_learning_path_skill"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    learning_path_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False, index=True)
    job_skill_gap_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_skill_gaps.id", ondelete="SET NULL"), nullable=True, index=True)
    skill_name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_skill: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    target_level: Mapped[str] = mapped_column(String(32), nullable=False, default="INTERVIEW_READY")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_STARTED")


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("learning_path_id", "normalized_skill", name="uq_course_learning_path_skill"),
        Index("ix_courses_user_job", "user_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    learning_path_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_skill: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="INTERMEDIATE")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_job_runs.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CourseModule(Base):
    __tablename__ = "course_modules"
    __table_args__ = (UniqueConstraint("course_id", "position", name="uq_course_module_position"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)


class CourseLesson(Base):
    __tablename__ = "course_lessons"
    __table_args__ = (UniqueConstraint("course_module_id", "position", name="uq_course_lesson_position"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    course_module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    key_points_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    resources_json: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)


class LessonConversation(Base):
    __tablename__ = "lesson_conversations"
    __table_args__ = (Index("ix_lesson_conversations_user_lesson", "user_id", "course_lesson_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()


class LearningExercise(Base):
    __tablename__ = "learning_exercises"
    __table_args__ = (Index("ix_learning_exercises_lesson_type", "course_lesson_id", "exercise_type"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    course_lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    answer_key_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False, default="ADAPTIVE")


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"
    __table_args__ = (Index("ix_exercise_attempts_user_exercise", "user_id", "learning_exercise_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    learning_exercise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SCORED")
    feedback_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "course_lesson_id", name="uq_learning_progress_user_lesson"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mastery_score: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewPack(Base):
    __tablename__ = "interview_packs"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "version", name="uq_interview_pack_user_job_version"),
        Index("ix_interview_packs_user_job", "user_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    strategy_summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_job_runs.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = created_at()


class InterviewPackSection(Base):
    __tablename__ = "interview_pack_sections"
    __table_args__ = (UniqueConstraint("interview_pack_id", "section_type", name="uq_interview_pack_section_type"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    interview_pack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_packs.id", ondelete="CASCADE"), nullable=False, index=True)
    section_type: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class MockInterviewSession(Base):
    __tablename__ = "mock_interview_sessions"
    __table_args__ = (Index("ix_mock_interviews_user_job_created", "user_id", "job_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    interview_pack_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("interview_packs.id", ondelete="SET NULL"), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="WRITTEN")
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False, default="ADAPTIVE")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="IN_PROGRESS")
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="applyai")
    provider_session_id: Mapped[str | None] = mapped_column(String(255))
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    category_scores_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    final_feedback_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = created_at()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()


class InterviewTurnRecord(Base):
    __tablename__ = "interview_turns"
    __table_args__ = (UniqueConstraint("interview_session_id", "position", name="uq_interview_turn_position"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    interview_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[str] = mapped_column(String(160), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text)
    follow_up: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score: Mapped[int | None] = mapped_column(Integer)
    evaluation_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()


class InterviewRecording(Base):
    __tablename__ = "interview_recordings"
    __table_args__ = (Index("ix_interview_recordings_session_created", "interview_session_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    interview_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="browser")
    created_at: Mapped[datetime] = created_at()


class CandidateSkillEvidence(Base):
    __tablename__ = "candidate_skill_evidence"
    __table_args__ = (Index("ix_candidate_skill_evidence_user_skill", "user_id", "normalized_skill", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    normalized_skill: Mapped[str] = mapped_column(String(160), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()


class CareerReadinessSnapshot(Base):
    __tablename__ = "career_readiness_snapshots"
    __table_args__ = (Index("ix_readiness_user_job_created", "user_id", "job_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    application_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    learning_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interview_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    breakdown_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()


class UsageLedger(Base):
    __tablename__ = "usage_ledger"
    __table_args__ = (Index("ix_usage_ledger_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("1"))
    related_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()
