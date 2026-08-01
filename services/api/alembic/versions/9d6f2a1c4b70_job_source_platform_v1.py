"""job source platform v1 registry and run metrics

Revision ID: 9d6f2a1c4b70
Revises: 8c4e91a7b2d3
Create Date: 2026-07-31 19:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "9d6f2a1c4b70"
down_revision: Union[str, None] = "8c4e91a7b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_source_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=48), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_identity", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("careers_url", sa.Text(), nullable=True),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "trust_level",
            sa.String(length=48),
            nullable=False,
            server_default="OFFICIAL_ATS",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("crawl_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_job_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "health_status",
            sa.String(length=32),
            nullable=False,
            server_default="HEALTHY",
        ),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_category", sa.String(length=48), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column(
            "crawl_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default="21600",
        ),
        sa.Column(
            "next_run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "source_identity",
            name="uq_job_source_registry_identity",
        ),
    )
    op.create_index(
        "ix_job_source_registry_company_id",
        "job_source_registry",
        ["company_id"],
    )
    op.create_index(
        "ix_job_source_registry_due",
        "job_source_registry",
        ["enabled", "next_run_at", "health_status"],
    )
    op.create_index(
        "ix_job_source_registry_lease",
        "job_source_registry",
        ["lease_expires_at", "locked_at"],
    )

    op.add_column(
        "job_ingestion_runs",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "job_ingestion_runs",
        sa.Column("source_type", sa.String(length=48), nullable=True),
    )
    op.add_column(
        "job_ingestion_runs",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "job_ingestion_runs",
        sa.Column("valid", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_ingestion_runs",
        sa.Column("invalid", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_ingestion_runs",
        sa.Column("deduplicated", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_ingestion_runs",
        sa.Column("error_category", sa.String(length=48), nullable=True),
    )
    op.add_column(
        "job_ingestion_runs",
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_job_ingestion_runs_source_id",
        "job_ingestion_runs",
        "job_source_registry",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_job_ingestion_runs_source_id",
        "job_ingestion_runs",
        ["source_id"],
    )
    op.create_index(
        "ix_job_ingestion_runs_source_type",
        "job_ingestion_runs",
        ["source_type"],
    )
    op.create_index(
        "ix_job_ingestion_runs_source_started",
        "job_ingestion_runs",
        ["source_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_ingestion_runs_source_started", table_name="job_ingestion_runs")
    op.drop_index("ix_job_ingestion_runs_source_type", table_name="job_ingestion_runs")
    op.drop_index("ix_job_ingestion_runs_source_id", table_name="job_ingestion_runs")
    op.drop_constraint(
        "fk_job_ingestion_runs_source_id",
        "job_ingestion_runs",
        type_="foreignkey",
    )
    op.drop_column("job_ingestion_runs", "error_summary")
    op.drop_column("job_ingestion_runs", "error_category")
    op.drop_column("job_ingestion_runs", "deduplicated")
    op.drop_column("job_ingestion_runs", "invalid")
    op.drop_column("job_ingestion_runs", "valid")
    op.drop_column("job_ingestion_runs", "duration_ms")
    op.drop_column("job_ingestion_runs", "source_type")
    op.drop_column("job_ingestion_runs", "source_id")

    op.drop_index("ix_job_source_registry_lease", table_name="job_source_registry")
    op.drop_index("ix_job_source_registry_due", table_name="job_source_registry")
    op.drop_index("ix_job_source_registry_company_id", table_name="job_source_registry")
    op.drop_table("job_source_registry")
