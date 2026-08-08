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


class JobSourceCapability(Base):
    """Operational/legal capability record for a job provider or marketplace.

    This table deliberately separates "we know this provider exists" from "ApplyAI is
    allowed and technically able to ingest it". Provider policy is data, not an
    assumption buried in crawler code.
    """

    __tablename__ = "job_source_capabilities"
    __table_args__ = (
        UniqueConstraint("provider_key", name="uq_job_source_capabilities_provider_key"),
        Index("ix_job_source_capabilities_mode_status", "access_mode", "implementation_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(48), nullable=False)
    implementation_status: Mapped[str] = mapped_column(String(48), nullable=False)

    official_api_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    public_feed_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    partner_feed_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    public_page_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    authentication_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    robots_policy: Mapped[str] = mapped_column(String(48), nullable=False, default="SOURCE_SPECIFIC")
    recommended_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    documentation_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    reviewed_at: Mapped[datetime] = created_at()
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OrganizationProfile(Base):
    """Scalable organization-universe metadata layered onto the canonical Company."""

    __tablename__ = "organization_profiles"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_organization_profiles_company_id"),
        UniqueConstraint("canonical_domain", name="uq_organization_profiles_canonical_domain"),
        Index("ix_organization_profiles_type_priority", "organization_type", "priority"),
        Index("ix_organization_profiles_status_priority", "source_status", "priority"),
        Index("ix_organization_profiles_country_region", "country_code", "state_region"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    canonical_domain: Mapped[str | None] = mapped_column(String(255))
    organization_type: Mapped[str] = mapped_column(String(48), nullable=False, default="COMPANY")
    industry: Mapped[str | None] = mapped_column(String(160))
    country_code: Mapped[str | None] = mapped_column(String(2))
    state_region: Mapped[str | None] = mapped_column(String(120))
    size_band: Mapped[str | None] = mapped_column(String(48))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    careers_url: Mapped[str | None] = mapped_column(Text)
    ats_provider: Mapped[str | None] = mapped_column(String(80))
    source_status: Mapped[str] = mapped_column(String(48), nullable=False, default="NEW")
    dataset_provenance: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class JobDedupCandidate(Base):
    """Persist non-exact cross-source duplicate evidence for auditable review."""

    __tablename__ = "job_dedup_candidates"
    __table_args__ = (
        UniqueConstraint("left_job_id", "right_job_id", name="uq_job_dedup_candidates_pair"),
        Index("ix_job_dedup_candidates_status_score", "status", "confidence_bps"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    left_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    right_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = created_at()
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
