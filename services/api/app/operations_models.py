from __future__ import annotations

import uuid
from datetime import datetime

from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OperationsCertification(Base):
    """Persisted evidence for operator/release certification decisions."""

    __tablename__ = "operations_certifications"
    __table_args__ = (
        Index("ix_operations_certifications_created", "created_at", "id"),
        Index("ix_operations_certifications_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certification_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(48), nullable=False, default="unknown")
    git_sha: Mapped[str | None] = mapped_column(String(64))
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ServiceCostEntry(Base):
    """Operator-recorded provider/service spend with source provenance."""

    __tablename__ = "service_cost_entries"
    __table_args__ = (
        Index("ix_service_cost_entries_period", "period_end", "period_start"),
        Index("ix_service_cost_entries_provider_period", "provider", "period_end"),
        Index("ix_service_cost_entries_category_period", "category", "period_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    cost_type: Mapped[str] = mapped_column(String(32), nullable=False, default="INVOICE")
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
