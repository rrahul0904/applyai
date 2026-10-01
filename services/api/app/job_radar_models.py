from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JobSearchProfile(Base):
    __tablename__ = "job_search_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_job_search_profiles_user"),
        Index("ix_job_search_profiles_user_confirmed", "user_id", "confirmed_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_titles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    skills: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    years_experience: Mapped[int | None] = mapped_column(Integer)
    seniority_preferences: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    preferred_locations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    remote_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="ANY")
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    query_hints: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class JobScan(Base):
    __tablename__ = "job_scans"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_job_scans_user_idempotency"),
        Index("ix_job_scans_user_created", "user_id", "created_at"),
        Index("ix_job_scans_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_search_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED", index=True)
    query_plan_json: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    provider_set_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    scoring_version: Mapped[str] = mapped_column(String(80), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    jobs_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_after_filter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_ranked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class JobScanMatch(Base):
    __tablename__ = "job_scan_matches"
    __table_args__ = (
        UniqueConstraint("scan_id", "job_id", name="uq_job_scan_matches_scan_job"),
        UniqueConstraint("scan_id", "rank", name="uq_job_scan_matches_scan_rank"),
        Index("ix_job_scan_matches_scan_score", "scan_id", "deterministic_score"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_job_id: Mapped[str | None] = mapped_column(String(255))
    application_url: Mapped[str] = mapped_column(Text, nullable=False)
    deterministic_score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_at()
