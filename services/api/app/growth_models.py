from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CandidatePortfolio(Base):
    """Explicitly opt-in public career portfolio configuration."""

    __tablename__ = "candidate_portfolios"
    __table_args__ = (
        UniqueConstraint("user_id"),
        UniqueConstraint("slug"),
        Index("ix_candidate_portfolios_public", "published", "slug"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    theme: Mapped[str] = mapped_column(String(32), nullable=False, default="PROFESSIONAL")
    indexing_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    headline: Mapped[str | None] = mapped_column(String(240), nullable=True)
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    contact_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CandidatePortfolioProject(Base):
    __tablename__ = "candidate_portfolio_projects"
    __table_args__ = (Index("ix_candidate_portfolio_projects_user_date", "user_id", "project_date"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(String(240), nullable=True)
    technologies: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    verified_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RecruiterLensCriteriaSet(Base):
    """Candidate-owned self-assessment criteria; never employer-side ranking configuration."""

    __tablename__ = "recruiter_lens_criteria_sets"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        Index("ix_recruiter_lens_criteria_sets_user_archived", "user_id", "archived"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="CUSTOM")
    criteria_json: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class InterviewPracticeAttempt(Base):
    __tablename__ = "interview_practice_attempts"
    __table_args__ = (
        Index("ix_interview_practice_user_job_created", "user_id", "job_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_review_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
