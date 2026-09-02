from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DatabaseObject(Base):
    """Small private object store for the hard-capped zero-cost pilot."""

    __tablename__ = "database_objects"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
