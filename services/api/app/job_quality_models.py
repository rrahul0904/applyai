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


class JobApplyUrlCheck(Base):
    __tablename__ = "job_apply_url_checks"
    __table_args__ = (
        Index("ix_job_apply_url_checks_due", "next_check_at", "status"),
        Index("ix_job_apply_url_checks_source_checked", "job_source_id", "checked_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    http_status: Mapped[int | None] = mapped_column(Integer)
    resolved_url: Mapped[str | None] = mapped_column(Text)
    response_ms: Mapped[int | None] = mapped_column(Integer)
    error_category: Mapped[str | None] = mapped_column(String(48))
    checked_at: Mapped[datetime] = created_at()
    next_check_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class JobClosureEvidence(Base):
    __tablename__ = "job_closure_evidence"
    __table_args__ = (
        Index("ix_job_closure_evidence_job_observed", "job_id", "observed_at"),
        UniqueConstraint(
            "job_id",
            "job_source_id",
            "evidence_type",
            "evidence_key",
            name="uq_job_closure_evidence_identity",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=True, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_key: Mapped[str] = mapped_column(String(128), nullable=False)
    strength: Mapped[str] = mapped_column(String(24), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    observed_at: Mapped[datetime] = created_at()


class JobFieldProvenance(Base):
    __tablename__ = "job_field_provenance"
    __table_args__ = (
        UniqueConstraint("job_id", "field_name", name="uq_job_field_provenance_field"),
        Index("ix_job_field_provenance_source_link", "job_source_link_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    job_source_link_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_source_links.id", ondelete="CASCADE"), nullable=False
    )
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    selected_at: Mapped[datetime] = created_at()


class IngestionCostObservation(Base):
    __tablename__ = "ingestion_cost_observations"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_ingestion_cost_observation_run"),
        Index("ix_ingestion_cost_observations_source_recorded", "source_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_ingestion_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_source_registry.id", ondelete="SET NULL"), nullable=True
    )
    worker_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    network_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_postings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    canonical_changes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    recorded_at: Mapped[datetime] = created_at()
