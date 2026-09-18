from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func
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



class OperationsServiceCost(Base):
    """Operator-maintained monthly FinOps ledger for the full ApplyAI service stack."""

    __tablename__ = "operations_service_costs"
    __table_args__ = (
        UniqueConstraint(
            "service_key",
            "environment",
            "billing_period",
            name="uq_operations_service_cost_service_env_period",
        ),
        Index(
            "ix_operations_service_cost_period_category",
            "billing_period",
            "category",
        ),
        Index(
            "ix_operations_service_cost_updated",
            "updated_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_key: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(48), nullable=False, default="production")
    billing_period: Mapped[str] = mapped_column(String(7), nullable=False)
    fixed_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credits_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    source: Mapped[str] = mapped_column(String(160), nullable=False, default="operator")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
