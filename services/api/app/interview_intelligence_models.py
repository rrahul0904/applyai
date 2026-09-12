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


class InterviewIntelligenceQuestion(Base):
    __tablename__ = "interview_intelligence_questions"
    __table_args__ = (
        Index("ix_interview_questions_track_published", "track", "published"),
        Index("ix_interview_questions_last_reported", "last_reported_at"),
        Index("ix_interview_questions_frequency", "frequency_score"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(240), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(320), nullable=False)
    track: Mapped[str] = mapped_column(String(48), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(24), nullable=False, default="MEDIUM")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    company_labels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    patterns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    hints: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    follow_ups: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    solution_outline: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    test_cases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    starter_code: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
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
        Index("ix_interview_reports_status_created", "moderation_status", "created_at"),
        Index("ix_interview_reports_company_reported", "company_label", "reported_at"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    contributor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[str | None] = mapped_column(String(320))
    company_label: Mapped[str | None] = mapped_column(String(240))
    role: Mapped[str | None] = mapped_column(String(240))
    interview_stage: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str | None] = mapped_column(String(320))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    license_status: Mapped[str] = mapped_column(String(48), nullable=False, default="USER_SUBMITTED")
    moderation_status: Mapped[str] = mapped_column(String(48), nullable=False, default="REVIEW_REQUIRED")
    extraction_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewQuestionEvidence(Base):
    __tablename__ = "interview_question_evidence"
    __table_args__ = (UniqueConstraint("question_id", "report_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_intelligence_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_intelligence_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class InterviewIntelligenceAttempt(Base):
    __tablename__ = "interview_intelligence_attempts"
    __table_args__ = (
        Index("ix_interview_attempts_user_question", "user_id", "question_id"),
        Index("ix_interview_attempts_user_job", "user_id", "job_id"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_intelligence_questions.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="IN_PROGRESS")
    language: Mapped[str | None] = mapped_column(String(48))
    answer: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    execution_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewPreparationPlan(Base):
    __tablename__ = "interview_preparation_plans"
    __table_args__ = (UniqueConstraint("user_id", "job_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    strengths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    gaps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewCommunityPost(Base):
    __tablename__ = "interview_community_posts"
    __table_args__ = (
        Index("ix_interview_community_created", "created_at"),
        Index("ix_interview_community_company_category", "company_label", "category"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_label: Mapped[str | None] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="INTERVIEW_EXPERIENCE")
    title: Mapped[str] = mapped_column(String(320), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(48), nullable=False, default="PUBLISHED")
    reaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterviewCommunityReply(Base):
    __tablename__ = "interview_community_replies"
    id: Mapped[uuid.UUID] = uuid_pk()
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_community_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(48), nullable=False, default="PUBLISHED")
    created_at: Mapped[datetime] = created_at()


class InterviewCommunityReaction(Base):
    __tablename__ = "interview_community_reactions"
    __table_args__ = (UniqueConstraint("post_id", "user_id", "reaction"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_community_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reaction: Mapped[str] = mapped_column(String(32), nullable=False, default="UPVOTE")
    created_at: Mapped[datetime] = created_at()
