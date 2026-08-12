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


class ApplicationQuestionMemory(Base):
    """Candidate-approved answer memory for recurring application questions.

    Answers are keyed by a canonical field rather than raw wording so variants such
    as "Will you require sponsorship?" and "Do you need visa sponsorship?" can use
    the same candidate-approved fact without asking again.
    """

    __tablename__ = "application_question_memory"
    __table_args__ = (
        UniqueConstraint("user_id", "canonical_key", name="uq_application_question_memory_user_key"),
        Index("ix_application_question_memory_user_verified", "user_id", "candidate_verified"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_key: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_question: Mapped[str | None] = mapped_column(Text)
    question_variants: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(String(32), nullable=False, default="TEXT")
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("1.0"))
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    candidate_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_kind: Mapped[str] = mapped_column(String(48), nullable=False, default="CANDIDATE")
    source_ref: Mapped[str | None] = mapped_column(String(255))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ApplicationExecution(Base):
    """Durable application-agent plan and browser-execution state.

    This state is intentionally separate from ``Application.current_status``. The
    existing application status tracks recruiting progress (APPLIED, INTERVIEW,
    OFFER, ...); this row tracks the technical apply workflow and its audit trail.
    """

    __tablename__ = "application_executions"
    __table_args__ = (
        UniqueConstraint("application_id", "attempt_number", name="uq_application_execution_attempt"),
        Index("ix_application_executions_user_state", "user_id", "state", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_copilot_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_artifacts.id", ondelete="SET NULL"), nullable=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="SMART")
    ats_provider: Mapped[str] = mapped_column(String(80), nullable=False, default="GENERIC")
    target_url: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="DISCOVERED", index=True)
    fields: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    review_items: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    missing_fields: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    documents: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    validation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    browser_handoff: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confirmation_url: Mapped[str | None] = mapped_column(Text)
    confirmation_text: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
