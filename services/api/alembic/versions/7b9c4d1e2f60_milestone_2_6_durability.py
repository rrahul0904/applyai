"""milestone 2.6 durability

Revision ID: 7b9c4d1e2f60
Revises: 0db19a1adb4d
Create Date: 2026-07-29 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "7b9c4d1e2f60"
down_revision: Union[str, None] = "0db19a1adb4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Previous upload behavior could create a new is_master=true Resume on every
    # replacement. Consolidate those rows before enforcing the invariant. Storage
    # keys stay untouched; ResumeVersion ids also stay stable for downstream FKs.
    op.execute(
        """
        WITH master_versions AS (
          SELECT
            rv.id,
            ROW_NUMBER() OVER (
              PARTITION BY r.user_id
              ORDER BY rv.created_at, rv.id
            ) AS seq
          FROM resume_versions rv
          JOIN resumes r ON r.id = rv.resume_id
          WHERE r.is_master IS TRUE
        )
        UPDATE resume_versions rv
        SET version_number = -mv.seq
        FROM master_versions mv
        WHERE rv.id = mv.id
        """
    )
    op.execute(
        """
        WITH ranked_masters AS (
          SELECT
            id,
            user_id,
            FIRST_VALUE(id) OVER (
              PARTITION BY user_id
              ORDER BY created_at, id
            ) AS canonical_id
          FROM resumes
          WHERE is_master IS TRUE
        )
        UPDATE resume_versions rv
        SET resume_id = rm.canonical_id
        FROM ranked_masters rm
        WHERE rv.resume_id = rm.id
          AND rm.id <> rm.canonical_id
        """
    )
    op.execute(
        """
        WITH ranked_masters AS (
          SELECT
            id,
            ROW_NUMBER() OVER (
              PARTITION BY user_id
              ORDER BY created_at, id
            ) AS rn
          FROM resumes
          WHERE is_master IS TRUE
        )
        DELETE FROM resumes r
        USING ranked_masters rm
        WHERE r.id = rm.id AND rm.rn > 1
        """
    )
    op.execute(
        """
        WITH renumbered AS (
          SELECT
            rv.id,
            ROW_NUMBER() OVER (
              PARTITION BY rv.resume_id
              ORDER BY rv.created_at, rv.id
            ) AS seq
          FROM resume_versions rv
          JOIN resumes r ON r.id = rv.resume_id
          WHERE r.is_master IS TRUE
        )
        UPDATE resume_versions rv
        SET version_number = rn.seq
        FROM renumbered rn
        WHERE rv.id = rn.id
        """
    )
    op.create_index(
        "uq_resumes_one_master_per_user",
        "resumes",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_master IS TRUE"),
    )

    # Old at-least-once processing could leave multiple extraction rows. Keep the
    # strongest/latest durable result for each version/parser before adding the
    # uniqueness guard used by the new idempotent processor.
    op.execute(
        """
        WITH ranked AS (
          SELECT
            id,
            ROW_NUMBER() OVER (
              PARTITION BY resume_version_id, parser_version
              ORDER BY
                CASE status
                  WHEN 'COMPLETED' THEN 4
                  WHEN 'NEEDS_REVIEW' THEN 3
                  WHEN 'PROCESSING' THEN 2
                  WHEN 'FAILED' THEN 1
                  ELSE 0
                END DESC,
                created_at DESC,
                id DESC
            ) AS rn
          FROM resume_extractions
        )
        DELETE FROM resume_extractions re
        USING ranked r
        WHERE re.id = r.id AND r.rn > 1
        """
    )
    op.create_index(
        "uq_resume_extractions_version_parser",
        "resume_extractions",
        ["resume_version_id", "parser_version"],
        unique=True,
    )

    op.create_table(
        "task_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_owner", sa.String(length=160), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_task_outbox_aggregate_id", "task_outbox", ["aggregate_id"])
    op.create_index("ix_task_outbox_available_at", "task_outbox", ["available_at"])
    op.create_index("ix_task_outbox_status", "task_outbox", ["status"])
    op.create_index(
        "ix_task_outbox_claim",
        "task_outbox",
        ["status", "available_at", "created_at"],
    )

    op.create_table(
        "resume_processing_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["resume_version_id"],
            ["resume_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resume_version_id",
            "parser_version",
            "attempt_number",
            name="uq_resume_processing_attempt",
        ),
    )
    op.create_index(
        "ix_resume_processing_attempts_resume_version_id",
        "resume_processing_attempts",
        ["resume_version_id"],
    )

    op.create_table(
        "job_ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector", sa.String(length=80), nullable=False),
        sa.Column("source_company", sa.String(length=255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RUNNING"),
        sa.Column("fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stale", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_ingestion_runs_connector", "job_ingestion_runs", ["connector"])
    op.create_index(
        "ix_job_ingestion_runs_source_company",
        "job_ingestion_runs",
        ["source_company"],
    )

    # Query-driven indexes introduced with the bounded application list and
    # source-to-canonical ingestion lookups.
    op.create_index(
        "ix_applications_user_updated_id",
        "applications",
        ["user_id", "updated_at", "id"],
    )
    op.create_index(
        "ix_job_source_links_job_source_id",
        "job_source_links",
        ["job_source_id"],
    )

    # Keep title/description lexical state safe even when a mutation happens outside
    # the ingestion service. Ingestion additionally refreshes the richer document
    # containing company, skills, and requirements.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION applyai_refresh_job_search_vector()
        RETURNS trigger AS $$
        BEGIN
          NEW.search_document := concat_ws(' ', NEW.title, NEW.description);
          NEW.search_vector := to_tsvector('english', coalesce(NEW.search_document, ''));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_applyai_refresh_job_search_vector
        BEFORE INSERT OR UPDATE OF title, description ON jobs
        FOR EACH ROW EXECUTE FUNCTION applyai_refresh_job_search_vector();
        """
    )
    op.execute(
        "UPDATE jobs SET search_document = concat_ws(' ', title, description), "
        "search_vector = to_tsvector('english', concat_ws(' ', title, description))"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_applyai_refresh_job_search_vector ON jobs")
    op.execute("DROP FUNCTION IF EXISTS applyai_refresh_job_search_vector()")

    op.drop_index("ix_job_source_links_job_source_id", table_name="job_source_links")
    op.drop_index("ix_applications_user_updated_id", table_name="applications")

    op.drop_index("ix_job_ingestion_runs_source_company", table_name="job_ingestion_runs")
    op.drop_index("ix_job_ingestion_runs_connector", table_name="job_ingestion_runs")
    op.drop_table("job_ingestion_runs")

    op.drop_index(
        "ix_resume_processing_attempts_resume_version_id",
        table_name="resume_processing_attempts",
    )
    op.drop_table("resume_processing_attempts")

    op.drop_index("ix_task_outbox_claim", table_name="task_outbox")
    op.drop_index("ix_task_outbox_status", table_name="task_outbox")
    op.drop_index("ix_task_outbox_available_at", table_name="task_outbox")
    op.drop_index("ix_task_outbox_aggregate_id", table_name="task_outbox")
    op.drop_table("task_outbox")

    op.drop_index("uq_resume_extractions_version_parser", table_name="resume_extractions")
    op.drop_index("uq_resumes_one_master_per_user", table_name="resumes")
