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


class InterviewIntelligenceWorkspace(Base):
    __tablename__ = "interview_intelligence_workspaces"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_interview_intelligence_workspace_user_job"),
        Index("ix_interview_intelligence_workspace_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    current_phase_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    interview_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interviewer_name: Mapped[str | None] = mapped_column(String(240))
    interviewer_title: Mapped[str | None] = mapped_column(String(240))
    interviewer_url: Mapped[str | None] = mapped_column(Text)
    lifecycle_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    readiness_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    podcast_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    research_sources_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


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


class InterviewIntelligenceQuestion(Base):
    __tablename__ = "interview_intelligence_questions"
    __table_args__ = (
        Index("ix_interview_intelligence_questions_slug", "slug", unique=True),
        Index("ix_interview_intelligence_questions_track_published", "track", "published"),
        Index("ix_interview_intelligence_questions_frequency", "frequency_score"),
        Index("ix_interview_intelligence_questions_last_reported", "last_reported_at"),
        Index("ix_interview_intelligence_questions_stages", "stages", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(240), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(320), nullable=False)
    track: Mapped[str] = mapped_column(String(48), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(24), nullable=False, default="MEDIUM")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_company_labels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    company_labels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    stages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    patterns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    hints: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    follow_ups: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    solution_outline: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    baseline_frequency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frequency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewIntelligenceReport(Base):
    __tablename__ = "interview_intelligence_reports"
    __table_args__ = (
        Index("ix_interview_intelligence_reports_fingerprint", "fingerprint", unique=True),
        Index("ix_interview_intelligence_reports_status_created", "moderation_status", "created_at"),
        Index("ix_interview_intelligence_reports_company_reported", "company_label", "reported_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    contributor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False, default="USER_SUBMISSION")
    source_reference: Mapped[str | None] = mapped_column(String(320))
    company_label: Mapped[str | None] = mapped_column(String(240))
    role: Mapped[str | None] = mapped_column(String(240))
    interview_stage: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str | None] = mapped_column(String(320))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    moderation_status: Mapped[str] = mapped_column(String(48), nullable=False, default="REVIEW_REQUIRED")
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewQuestionEvidence(Base):
    __tablename__ = "interview_question_evidence"
    __table_args__ = (UniqueConstraint("question_id", "report_id", name="uq_interview_question_evidence_pair"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_intelligence_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_intelligence_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    evidence_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class InterviewQuestionAttempt(Base):
    __tablename__ = "interview_question_attempts"
    __table_args__ = (
        Index("ix_interview_question_attempts_user_question", "user_id", "question_id", "created_at"),
        Index("ix_interview_question_attempts_user_job", "user_id", "job_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_intelligence_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    answer_text: Mapped[str | None] = mapped_column(Text)
    code_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="IN_PROGRESS")
    score: Mapped[int | None] = mapped_column(Integer)
    feedback_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewCommunityPost(Base):
    __tablename__ = "interview_community_posts"
    __table_args__ = (
        Index("ix_interview_community_posts_created", "created_at"),
        Index("ix_interview_community_posts_company_category", "company_label", "category"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_label: Mapped[str | None] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="INTERVIEW_EXPERIENCE")
    title: Mapped[str] = mapped_column(String(320), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    replies_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reaction_user_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    moderation_status: Mapped[str] = mapped_column(String(48), nullable=False, default="PUBLISHED")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
