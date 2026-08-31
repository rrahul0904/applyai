from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResumeShareLink(Base):
    """Candidate-owned, revocable public link to a resume version or current resume."""

    __tablename__ = "resume_share_links"
    __table_args__ = (
        Index("ix_resume_share_links_user_status_created", "user_id", "status", "created_at"),
        Index("ix_resume_share_links_job_created", "job_id", "created_at"),
        Index("ix_resume_share_links_application_created", "application_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pinned_resume_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    public_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(80), nullable=True)
    always_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_download: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ResumeShareEvent(Base):
    """Privacy-preserving engagement event for one public resume link.

    session_hash is scoped to a single share link. Raw IP addresses and browser fingerprints are not
    persisted by this feature.
    """

    __tablename__ = "resume_share_events"
    __table_args__ = (
        Index("ix_resume_share_events_share_time", "share_id", "occurred_at"),
        Index("ix_resume_share_events_share_session", "share_id", "session_hash", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    share_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_share_links.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    suspected_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    occurred_at: Mapped[datetime] = created_at()
