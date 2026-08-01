"""job data scale quality controls

Revision ID: b2f8d5e6a390
Revises: a1e7c9d4f280
Create Date: 2026-08-01 00:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2f8d5e6a390"
down_revision: Union[str, None] = "a1e7c9d4f280"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_job_source_registry_due", table_name="job_source_registry")
    op.add_column(
        "job_source_registry",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "job_source_registry",
        sa.Column("last_dispatch_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "job_source_registry",
        sa.Column("last_change_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_source_registry",
        sa.Column("min_interval_seconds", sa.Integer(), nullable=False, server_default="900"),
    )
    op.add_column(
        "job_source_registry",
        sa.Column("max_interval_seconds", sa.Integer(), nullable=False, server_default="604800"),
    )
    op.create_index(
        "ix_job_source_registry_due",
        "job_source_registry",
        ["enabled", "next_run_at", "priority", "health_status"],
    )

    op.create_table(
        "job_apply_url_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("resolved_url", sa.Text(), nullable=True),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=48), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_source_id"], ["job_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_apply_url_checks_job_source_id", "job_apply_url_checks", ["job_source_id"])
    op.create_index("ix_job_apply_url_checks_next_check_at", "job_apply_url_checks", ["next_check_at"])
    op.create_index("ix_job_apply_url_checks_due", "job_apply_url_checks", ["next_check_at", "status"])
    op.create_index(
        "ix_job_apply_url_checks_source_checked",
        "job_apply_url_checks",
        ["job_source_id", "checked_at"],
    )

    op.create_table(
        "job_closure_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=48), nullable=False),
        sa.Column("evidence_key", sa.String(length=128), nullable=False),
        sa.Column("strength", sa.String(length=24), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_source_id"], ["job_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "job_source_id",
            "evidence_type",
            "evidence_key",
            name="uq_job_closure_evidence_identity",
        ),
    )
    op.create_index("ix_job_closure_evidence_job_id", "job_closure_evidence", ["job_id"])
    op.create_index("ix_job_closure_evidence_job_source_id", "job_closure_evidence", ["job_source_id"])
    op.create_index(
        "ix_job_closure_evidence_job_observed",
        "job_closure_evidence",
        ["job_id", "observed_at"],
    )

    op.create_table(
        "job_field_provenance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("job_source_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value_hash", sa.String(length=64), nullable=False),
        sa.Column("selection_reason", sa.String(length=120), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_source_link_id"], ["job_source_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "field_name", name="uq_job_field_provenance_field"),
    )
    op.create_index("ix_job_field_provenance_job_id", "job_field_provenance", ["job_id"])
    op.create_index(
        "ix_job_field_provenance_source_link",
        "job_field_provenance",
        ["job_source_link_id"],
    )

    op.create_table(
        "ingestion_cost_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("worker_seconds", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("network_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_postings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("canonical_changes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["run_id"], ["job_ingestion_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["job_source_registry.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_ingestion_cost_observation_run"),
    )
    op.create_index(
        "ix_ingestion_cost_observations_source_recorded",
        "ingestion_cost_observations",
        ["source_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_cost_observations_source_recorded", table_name="ingestion_cost_observations")
    op.drop_table("ingestion_cost_observations")
    op.drop_index("ix_job_field_provenance_source_link", table_name="job_field_provenance")
    op.drop_index("ix_job_field_provenance_job_id", table_name="job_field_provenance")
    op.drop_table("job_field_provenance")
    op.drop_index("ix_job_closure_evidence_job_observed", table_name="job_closure_evidence")
    op.drop_index("ix_job_closure_evidence_job_source_id", table_name="job_closure_evidence")
    op.drop_index("ix_job_closure_evidence_job_id", table_name="job_closure_evidence")
    op.drop_table("job_closure_evidence")
    op.drop_index("ix_job_apply_url_checks_source_checked", table_name="job_apply_url_checks")
    op.drop_index("ix_job_apply_url_checks_due", table_name="job_apply_url_checks")
    op.drop_index("ix_job_apply_url_checks_next_check_at", table_name="job_apply_url_checks")
    op.drop_index("ix_job_apply_url_checks_job_source_id", table_name="job_apply_url_checks")
    op.drop_table("job_apply_url_checks")
    op.drop_index("ix_job_source_registry_due", table_name="job_source_registry")
    op.drop_column("job_source_registry", "max_interval_seconds")
    op.drop_column("job_source_registry", "min_interval_seconds")
    op.drop_column("job_source_registry", "last_change_count")
    op.drop_column("job_source_registry", "last_dispatch_at")
    op.drop_column("job_source_registry", "priority")
    op.create_index(
        "ix_job_source_registry_due",
        "job_source_registry",
        ["enabled", "next_run_at", "health_status"],
    )
