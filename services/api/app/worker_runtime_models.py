from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkerRuntimeHeartbeat(Base):
    """Latest durable liveness receipt for one worker process instance."""

    __tablename__ = "worker_runtime_heartbeats"
    __table_args__ = (
        UniqueConstraint(
            "environment",
            "worker_type",
            "worker_id",
            name="uq_worker_runtime_heartbeats_instance",
        ),
        Index(
            "ix_worker_runtime_heartbeats_lookup",
            "environment",
            "worker_type",
            "heartbeat_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    environment: Mapped[str] = mapped_column(String(48), nullable=False)
    worker_type: Mapped[str] = mapped_column(String(80), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(160), nullable=False)
    deployment_sha: Mapped[str | None] = mapped_column(String(64))
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
