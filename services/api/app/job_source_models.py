from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JobSourceRegistry(Base):
    """A fetchable employer board, career site, or feed."""

    __tablename__ = "job_source_registry"
    __table_args__ = (
        UniqueConstraint("source_type", "source_identity", name="uq_job_source_registry_identity"),
        Index("ix_job_source_registry_due", "enabled", "next_run_at", "health_status"),
        Index("ix_job_source_registry_lease", "lease_expires_at", "locked_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    careers_url: Mapped[str | None] = mapped_column(Text)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trust_level: Mapped[str] = mapped_column(String(48), nullable=False, default="OFFICIAL_ATS")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    crawl_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    discovered_at: Mapped[datetime] = created_at()
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_job_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="HEALTHY")
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_category: Mapped[str | None] = mapped_column(String(48))
    last_error_summary: Mapped[str | None] = mapped_column(Text)

    crawl_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=21_600)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class JobSourceDiscovery(Base):
    """One bounded discovery or candidate-submitted public job URL attempt."""

    __tablename__ = "job_source_discoveries"
    __table_args__ = (
        Index("ix_job_source_discoveries_user_created", "user_id", "created_at"),
        Index("ix_job_source_discoveries_status_created", "status", "created_at"),
        Index("ix_job_source_discoveries_domain", "input_domain", "status"),
        UniqueConstraint("request_key", name="uq_job_source_discoveries_request_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_registry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_source_registry.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    input_url: Mapped[str] = mapped_column(Text, nullable=False)
    input_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    discovered_careers_url: Mapped[str | None] = mapped_column(Text)
    discovered_url: Mapped[str | None] = mapped_column(Text)
    resolved_url: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    apply_url: Mapped[str | None] = mapped_column(Text)

    detected_provider: Mapped[str | None] = mapped_column(String(48))
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    access_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_category: Mapped[str | None] = mapped_column(String(48))
    error_summary: Mapped[str | None] = mapped_column(Text)

    discovered_at: Mapped[datetime] = created_at()
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
