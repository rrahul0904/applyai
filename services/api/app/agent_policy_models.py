from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentRuntimePolicy(Base):
    __tablename__ = "agent_runtime_policies"
    __table_args__ = (
        UniqueConstraint("agent_name", "agent_version", name="uq_agent_runtime_policy_definition"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled_override: Mapped[bool | None] = mapped_column(Boolean)
    max_cost_usd_override: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
