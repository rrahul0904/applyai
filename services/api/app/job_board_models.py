from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JobBoard(Base):
    """A public/operator-facing board composed from ApplyAI's canonical job sources."""

    __tablename__ = "job_boards"
    __table_args__ = (
        Index("ix_job_boards_status_visibility", "status", "visibility"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="PUBLIC")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class JobBoardSource(Base):
    """Membership of an existing registered source in a public job board."""

    __tablename__ = "job_board_sources"
    __table_args__ = (
        UniqueConstraint("board_id", "source_registry_id", name="uq_job_board_sources_membership"),
        Index("ix_job_board_sources_source", "source_registry_id", "enabled"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    board_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_registry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_source_registry.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    label: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = created_at()


class JobBoardClaim(Base):
    """Auditable ownership claim; verification and approval are separate state transitions."""

    __tablename__ = "job_board_claims"
    __table_args__ = (
        Index("ix_job_board_claims_board_status", "board_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    board_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claimant_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    proof_method: Mapped[str] = mapped_column(String(48), nullable=False, default="DOMAIN")
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    review_notes: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = created_at()
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobOutboundClick(Base):
    """Privacy-minimized attribution receipt for a user leaving ApplyAI for an application URL."""

    __tablename__ = "job_outbound_clicks"
    __table_args__ = (
        Index("ix_job_outbound_clicks_board_created", "board_id", "created_at"),
        Index("ix_job_outbound_clicks_job_created", "job_id", "created_at"),
        Index("ix_job_outbound_clicks_channel_created", "channel", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_boards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_registry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_source_registry.id", ondelete="SET NULL"), nullable=True
    )
    destination_url: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(48), nullable=False, default="DIRECT")
    referrer_host: Mapped[str | None] = mapped_column(String(255))
    session_hash: Mapped[str | None] = mapped_column(String(64))
    attribution: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()


class JobDistributionPublication(Base):
    """Idempotent publication intent/receipt for external job distribution channels."""

    __tablename__ = "job_distribution_publications"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_job_distribution_publications_idempotency"),
        Index("ix_job_distribution_publications_status_channel", "status", "channel"),
        Index("ix_job_distribution_publications_board_created", "board_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_boards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(48), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_id: Mapped[str | None] = mapped_column(String(255))
    external_url: Mapped[str | None] = mapped_column(Text)
    receipt_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class JobSponsorshipCampaign(Base):
    __tablename__ = "job_sponsorship_campaigns"
    __table_args__ = (
        Index("ix_job_sponsorship_campaigns_status_window", "status", "starts_at", "ends_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_boards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    sponsor_name: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    destination_url: Mapped[str | None] = mapped_column(Text)
    budget_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spent_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class JobSponsorshipPlacement(Base):
    __tablename__ = "job_sponsorship_placements"
    __table_args__ = (
        UniqueConstraint("campaign_id", "slot", "job_id", name="uq_job_sponsorship_placements_slot_job"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_sponsorship_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_boards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    slot: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = created_at()


class JobSeoAudit(Base):
    __tablename__ = "job_seo_audits"
    __table_args__ = (
        Index("ix_job_seo_audits_job_created", "job_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_boards.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PASS")
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    issues: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    schema_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()


class SearchConsoleSnapshot(Base):
    __tablename__ = "search_console_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "property_uri",
            "snapshot_date",
            "dimension_key",
            "dimension_value",
            name="uq_search_console_snapshots_dimension",
        ),
        Index("ix_search_console_snapshots_board_date", "board_id", "snapshot_date"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_boards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    property_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    dimension_key: Mapped[str] = mapped_column(String(48), nullable=False, default="page")
    dimension_value: Mapped[str] = mapped_column(Text, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ctr: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    position: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at()
