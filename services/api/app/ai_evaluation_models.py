from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIEvaluationReceipt(Base):
    __tablename__ = "ai_evaluation_receipts"
    __table_args__ = (
        UniqueConstraint("receipt_digest", name="uq_ai_evaluation_receipts_digest"),
        Index(
            "ix_ai_evaluation_receipts_subject",
            "subject_type",
            "subject_name",
            "subject_version",
            "created_at",
        ),
        Index("ix_ai_evaluation_receipts_gate_verdict", "release_gate", "verdict"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(160), nullable=False)
    subject_version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(120), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    release_gate: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    scored_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    wins: Mapped[int] = mapped_column(Integer, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, nullable=False)
    ties: Mapped[int] = mapped_column(Integer, nullable=False)
    net_lift: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    sign_p: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    trigger_precision: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
    trigger_recall: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
    baseline_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    candidate_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    cost_delta_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    baseline_duration_ms: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    candidate_duration_ms: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    duration_delta_ms: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    receipt_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    receipt_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provenance_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
