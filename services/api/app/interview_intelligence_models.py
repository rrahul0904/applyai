from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class InterviewPreparation(Base):
    __tablename__ = "interview_preparations"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_interview_preparations_user_job"),
        Index("ix_interview_preparations_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    country: Mapped[str | None] = mapped_column(String(120))
    interview_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_phase_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    interviewer_name: Mapped[str | None] = mapped_column(String(240))
    interviewer_title: Mapped[str | None] = mapped_column(String(240))
    interviewer_url: Mapped[str | None] = mapped_column(Text)
    company_research: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    role_analysis: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resume_analysis: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    market_benchmark: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    interviewer_brief: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    readiness: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    private_feed_token: Mapped[str] = mapped_column(String(96), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewPhase(Base):
    __tablename__ = "interview_phases"
    __table_args__ = (
        UniqueConstraint("preparation_id", "phase_number", name="uq_interview_phase_number"),
        Index("ix_interview_phases_preparation_status", "preparation_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    preparation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_preparations.id", ondelete="CASCADE"), nullable=False, index=True)
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_type: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPCOMING")
    prep: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    quiz: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    flashcards: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    reflection: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cheat_sheet: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    readiness: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewPodcastEpisode(Base):
    __tablename__ = "interview_podcast_episodes"
    __table_args__ = (
        UniqueConstraint("preparation_id", "episode_number", name="uq_interview_episode_number"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    preparation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_preparations.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    script: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    duration_estimate_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    audio_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SCRIPT_READY")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewPracticeQuestion(Base):
    __tablename__ = "interview_practice_questions"
    __table_args__ = (Index("ix_interview_questions_phase_order", "phase_id", "display_order"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    phase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_phases.id", ondelete="CASCADE"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(48), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_answer: Mapped[str] = mapped_column(Text, nullable=False)
    rubric: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    followups: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = created_at()


class InterviewPracticeAttempt(Base):
    __tablename__ = "interview_practice_attempts"
    __table_args__ = (Index("ix_interview_attempts_user_question_time", "user_id", "question_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_practice_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_source: Mapped[str] = mapped_column(String(32), nullable=False, default="TEXT")
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()


class InterviewResearchSource(Base):
    __tablename__ = "interview_research_sources"
    __table_args__ = (Index("ix_interview_research_preparation_kind", "preparation_id", "source_kind"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    preparation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_preparations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(320), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()


class InterviewStory(Base):
    __tablename__ = "interview_stories"
    __table_args__ = (Index("ix_interview_stories_user_updated", "user_id", "updated_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    categories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    situation: Mapped[str | None] = mapped_column(Text)
    task: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_fact_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
