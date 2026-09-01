from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecruiterLensReportShare(Base):
    """Candidate-controlled private share link for a Recruiter Lens self-assessment report."""

    __tablename__ = "recruiter_lens_report_shares"
    __table_args__ = (
        Index("ix_recruiter_lens_report_shares_user_created", "user_id", "created_at"),
        Index("ix_recruiter_lens_report_shares_active_token", "revoked", "public_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criteria_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recruiter_lens_criteria_sets.id", ondelete="SET NULL"), nullable=True
    )
    public_token: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="DEFAULT_RECRUITER")
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
