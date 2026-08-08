"""global job supply capabilities and organization universe

Revision ID: h8f2d4e7a975
Revises: g7e1c3d6f864
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "h8f2d4e7a975"
down_revision: str | None = "g7e1c3d6f864"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_source_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("access_mode", sa.String(length=48), nullable=False),
        sa.Column("implementation_status", sa.String(length=48), nullable=False),
        sa.Column("official_api_available", sa.Boolean(), nullable=False),
        sa.Column("public_feed_available", sa.Boolean(), nullable=False),
        sa.Column("partner_feed_available", sa.Boolean(), nullable=False),
        sa.Column("public_page_access", sa.Boolean(), nullable=False),
        sa.Column("authentication_required", sa.Boolean(), nullable=False),
        sa.Column("robots_policy", sa.String(length=48), nullable=False),
        sa.Column("recommended_strategy", sa.Text(), nullable=False),
        sa.Column("documentation_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key", name="uq_job_source_capabilities_provider_key"),
    )
    op.create_index(
        "ix_job_source_capabilities_mode_status",
        "job_source_capabilities",
        ["access_mode", "implementation_status"],
        unique=False,
    )

    op.create_table(
        "organization_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_domain", sa.String(length=255), nullable=True),
        sa.Column("organization_type", sa.String(length=48), nullable=False),
        sa.Column("industry", sa.String(length=160), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("state_region", sa.String(length=120), nullable=True),
        sa.Column("size_band", sa.String(length=48), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("careers_url", sa.Text(), nullable=True),
        sa.Column("ats_provider", sa.String(length=80), nullable=True),
        sa.Column("source_status", sa.String(length=48), nullable=False),
        sa.Column("dataset_provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_domain", name="uq_organization_profiles_canonical_domain"),
        sa.UniqueConstraint("company_id", name="uq_organization_profiles_company_id"),
    )
    op.create_index(
        "ix_organization_profiles_type_priority",
        "organization_profiles",
        ["organization_type", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_organization_profiles_status_priority",
        "organization_profiles",
        ["source_status", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_organization_profiles_country_region",
        "organization_profiles",
        ["country_code", "state_region"],
        unique=False,
    )

    op.create_table(
        "job_dedup_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("left_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("right_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["left_job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["right_job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("left_job_id", "right_job_id", name="uq_job_dedup_candidates_pair"),
    )
    op.create_index("ix_job_dedup_candidates_left_job_id", "job_dedup_candidates", ["left_job_id"], unique=False)
    op.create_index("ix_job_dedup_candidates_right_job_id", "job_dedup_candidates", ["right_job_id"], unique=False)
    op.create_index(
        "ix_job_dedup_candidates_status_score",
        "job_dedup_candidates",
        ["status", "confidence_bps"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_dedup_candidates_status_score", table_name="job_dedup_candidates")
    op.drop_index("ix_job_dedup_candidates_right_job_id", table_name="job_dedup_candidates")
    op.drop_index("ix_job_dedup_candidates_left_job_id", table_name="job_dedup_candidates")
    op.drop_table("job_dedup_candidates")
    op.drop_index("ix_organization_profiles_country_region", table_name="organization_profiles")
    op.drop_index("ix_organization_profiles_status_priority", table_name="organization_profiles")
    op.drop_index("ix_organization_profiles_type_priority", table_name="organization_profiles")
    op.drop_table("organization_profiles")
    op.drop_index("ix_job_source_capabilities_mode_status", table_name="job_source_capabilities")
    op.drop_table("job_source_capabilities")
