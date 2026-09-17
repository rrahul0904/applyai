from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReverseEngineeringTopic(Base):
    __tablename__ = "reverse_engineering_topics"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_reverse_engineering_topics_source_url"),
        Index("ix_reverse_engineering_topics_fit_status", "applyai_fit", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False, default="PUBLIC_RESEARCH")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    applyai_fit: Mapped[str] = mapped_column(String(32), nullable=False)
    fit_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    destination: Mapped[str] = mapped_column(String(80), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(32), nullable=False)
    classification_source: Mapped[str] = mapped_column(String(16), nullable=False, default="AUTO")
    candidate_journey_stages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    qualifying_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    excluded_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RESEARCHED")
    implementation_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
