"""add job board network, distribution and attribution

Revision ID: a7s1w3x6t864
Revises: z6r0v2o5s753
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7s1w3x6t864"
down_revision: str | None = "z6r0v2o5s753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_boards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(180), nullable=False, unique=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("website_url", sa.Text()),
        sa.Column("logo_url", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("visibility", sa.String(32), nullable=False, server_default="PUBLIC"),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_boards_status_visibility", "job_boards", ["status", "visibility"])
    op.create_index("ix_job_boards_owner_user_id", "job_boards", ["owner_user_id"])

    op.create_table(
        "job_board_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_registry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_source_registry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("label", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("board_id", "source_registry_id", name="uq_job_board_sources_membership"),
    )
    op.create_index("ix_job_board_sources_board_id", "job_board_sources", ["board_id"])
    op.create_index("ix_job_board_sources_source_registry_id", "job_board_sources", ["source_registry_id"])
    op.create_index("ix_job_board_sources_source", "job_board_sources", ["source_registry_id", "enabled"])

    op.create_table(
        "job_board_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claimant_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("proof_method", sa.String(48), nullable=False, server_default="DOMAIN"),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("review_notes", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_job_board_claims_board_id", "job_board_claims", ["board_id"])
    op.create_index("ix_job_board_claims_claimant_user_id", "job_board_claims", ["claimant_user_id"])
    op.create_index("ix_job_board_claims_board_status", "job_board_claims", ["board_id", "status"])

    op.create_table(
        "job_outbound_clicks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id", ondelete="SET NULL")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("source_registry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_source_registry.id", ondelete="SET NULL")),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(48), nullable=False, server_default="DIRECT"),
        sa.Column("referrer_host", sa.String(255)),
        sa.Column("session_hash", sa.String(64)),
        sa.Column("attribution", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_outbound_clicks_job_id", "job_outbound_clicks", ["job_id"])
    op.create_index("ix_job_outbound_clicks_board_id", "job_outbound_clicks", ["board_id"])
    op.create_index("ix_job_outbound_clicks_user_id", "job_outbound_clicks", ["user_id"])
    op.create_index("ix_job_outbound_clicks_board_created", "job_outbound_clicks", ["board_id", "created_at"])
    op.create_index("ix_job_outbound_clicks_job_created", "job_outbound_clicks", ["job_id", "created_at"])
    op.create_index("ix_job_outbound_clicks_channel_created", "job_outbound_clicks", ["channel", "created_at"])

    op.create_table(
        "job_distribution_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id", ondelete="SET NULL")),
        sa.Column("channel", sa.String(48), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("external_id", sa.String(255)),
        sa.Column("external_url", sa.Text()),
        sa.Column("receipt_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_job_distribution_publications_idempotency"),
    )
    op.create_index("ix_job_distribution_publications_job_id", "job_distribution_publications", ["job_id"])
    op.create_index("ix_job_distribution_publications_board_id", "job_distribution_publications", ["board_id"])
    op.create_index("ix_job_distribution_publications_status_channel", "job_distribution_publications", ["status", "channel"])
    op.create_index("ix_job_distribution_publications_board_created", "job_distribution_publications", ["board_id", "created_at"])

    op.create_table(
        "job_sponsorship_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("sponsor_name", sa.String(180), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("destination_url", sa.Text()),
        sa.Column("budget_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spent_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_sponsorship_campaigns_board_id", "job_sponsorship_campaigns", ["board_id"])
    op.create_index("ix_job_sponsorship_campaigns_status_window", "job_sponsorship_campaigns", ["status", "starts_at", "ends_at"])

    op.create_table(
        "job_sponsorship_placements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_sponsorship_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id", ondelete="SET NULL")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("slot", sa.String(80), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("campaign_id", "slot", "job_id", name="uq_job_sponsorship_placements_slot_job"),
    )
    op.create_index("ix_job_sponsorship_placements_campaign_id", "job_sponsorship_placements", ["campaign_id"])
    op.create_index("ix_job_sponsorship_placements_board_id", "job_sponsorship_placements", ["board_id"])
    op.create_index("ix_job_sponsorship_placements_job_id", "job_sponsorship_placements", ["job_id"])

    op.create_table(
        "job_seo_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False, server_default="PASS"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("issues", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("schema_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_seo_audits_job_id", "job_seo_audits", ["job_id"])
    op.create_index("ix_job_seo_audits_job_created", "job_seo_audits", ["job_id", "created_at"])

    op.create_table(
        "search_console_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_boards.id", ondelete="SET NULL")),
        sa.Column("property_uri", sa.String(500), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("dimension_key", sa.String(48), nullable=False, server_default="page"),
        sa.Column("dimension_value", sa.Text(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ctr", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("position", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("property_uri", "snapshot_date", "dimension_key", "dimension_value", name="uq_search_console_snapshots_dimension"),
    )
    op.create_index("ix_search_console_snapshots_board_id", "search_console_snapshots", ["board_id"])
    op.create_index("ix_search_console_snapshots_board_date", "search_console_snapshots", ["board_id", "snapshot_date"])


def downgrade() -> None:
    op.drop_table("search_console_snapshots")
    op.drop_table("job_seo_audits")
    op.drop_table("job_sponsorship_placements")
    op.drop_table("job_sponsorship_campaigns")
    op.drop_table("job_distribution_publications")
    op.drop_table("job_outbound_clicks")
    op.drop_table("job_board_claims")
    op.drop_table("job_board_sources")
    op.drop_table("job_boards")
