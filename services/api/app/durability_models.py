from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models import Application, JobSourceLink, Resume, ResumeExtraction


# Keep Alembic metadata aligned with explicit integrity/performance indexes introduced
# in the Milestone 2.6 migration. Each one corresponds to a current query path.
Index(
    "uq_resumes_one_master_per_user",
    Resume.__table__.c.user_id,
    unique=True,
    postgresql_where=Resume.__table__.c.is_master.is_(True),
)
Index(
    "uq_resume_extractions_version_parser",
    ResumeExtraction.__table__.c.resume_version_id,
    ResumeExtraction.__table__.c.parser_version,
    unique=True,
)
# PostgreSQL can scan this B-tree backward for the updated_at/id descending keyset
# order once user_id is fixed by equality, so a portable ascending definition is enough.
Index(
    "ix_applications_user_updated_id",
    Application.__table__.c.user_id,
    Application.__table__.c.updated_at,
    Application.__table__.c.id,
)
Index(
    "ix_job_source_links_job_source_id",
    JobSourceLink.__table__.c.job_source_id,
)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TaskOutbox(Base):
    __tablename__ = "task_outbox"
    __table_args__ = (
        Index("ix_task_outbox_claim", "status", "available_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_owner: Mapped[str | None] = mapped_column(String(160))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class ResumeProcessingAttempt(Base):
    __tablename__ = "resume_processing_attempts"
    __table_args__ = (
        UniqueConstraint(
            "resume_version_id", "parser_version", "attempt_number",
            name="uq_resume_processing_attempt",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class JobIngestionRun(Base):
    __tablename__ = "job_ingestion_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    connector: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING")
    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stale: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
