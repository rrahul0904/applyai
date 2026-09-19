from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class RadarWatch(Base):
    __tablename__ = "radar_watches"
    __table_args__ = (
        Index("ix_radar_watches_due", "enabled", "next_run_at", "id"),
        Index("ix_radar_watches_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    max_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_status: Mapped[str | None] = mapped_column(String(32))
    last_scheduled_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RadarBucketTransition(Base):
    __tablename__ = "radar_bucket_transitions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "job_id",
            "engine_version",
            "model_run_id",
            name="uq_radar_bucket_transition_run",
        ),
        Index("ix_radar_bucket_transitions_user_created", "user_id", "created_at", "id"),
        Index("ix_radar_bucket_transitions_job_created", "job_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("career_matches.id", ondelete="SET NULL"), nullable=True
    )
    model_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_job_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    from_bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    to_bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    from_decision: Mapped[str | None] = mapped_column(String(32))
    to_decision: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
