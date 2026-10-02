"""Persist Job Radar search profiles, scans, and deterministic matches.

Revision ID: a7s1w3p6t864
Revises: z6r0v2o5s753
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7s1w3p6t864"
down_revision: str | None = "z6r0v2o5s753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_search_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "resume_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("resume_versions.id", ondelete="SET NULL"),
        ),
        sa.Column("target_titles", postgresql.JSONB(), nullable=False),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("years_experience", sa.Integer()),
        sa.Column("seniority_preferences", postgresql.JSONB(), nullable=False),
        sa.Column("preferred_locations", postgresql.JSONB(), nullable=False),
        sa.Column("remote_policy", sa.String(32), nullable=False, server_default="ANY"),
        sa.Column("salary_min", sa.Integer()),
        sa.Column("salary_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "query_hints",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", name="uq_job_search_profiles_user"),
    )
    op.create_index("ix_job_search_profiles_user_id", "job_search_profiles", ["user_id"])
    op.create_index(
        "ix_job_search_profiles_resume_version_id",
        "job_search_profiles",
        ["resume_version_id"],
    )
    op.create_index(
        "ix_job_search_profiles_user_confirmed",
        "job_search_profiles",
        ["user_id", "confirmed_at"],
    )

    op.create_table(
        "job_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_search_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("query_plan_json", postgresql.JSONB(), nullable=False),
        sa.Column("provider_set_json", postgresql.JSONB(), nullable=False),
        sa.Column("scoring_version", sa.String(80), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("jobs_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_after_filter", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_ranked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_detail", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_job_scans_user_idempotency"),
    )
    op.create_index("ix_job_scans_user_id", "job_scans", ["user_id"])
    op.create_index("ix_job_scans_profile_id", "job_scans", ["profile_id"])
    op.create_index("ix_job_scans_status", "job_scans", ["status"])
    op.create_index("ix_job_scans_user_created", "job_scans", ["user_id", "created_at"])
    op.create_index("ix_job_scans_status_created", "job_scans", ["status", "created_at"])

    op.create_table(
        "job_scan_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_job_id", sa.String(255)),
        sa.Column("application_url", sa.Text(), nullable=False),
        sa.Column("deterministic_score", sa.Integer(), nullable=False),
        sa.Column("score_breakdown", postgresql.JSONB(), nullable=False),
        sa.Column("source_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("scan_id", "job_id", name="uq_job_scan_matches_scan_job"),
        sa.UniqueConstraint("scan_id", "rank", name="uq_job_scan_matches_scan_rank"),
    )
    op.create_index("ix_job_scan_matches_scan_id", "job_scan_matches", ["scan_id"])
    op.create_index("ix_job_scan_matches_job_id", "job_scan_matches", ["job_id"])
    op.create_index(
        "ix_job_scan_matches_scan_score",
        "job_scan_matches",
        ["scan_id", "deterministic_score"],
    )


def downgrade() -> None:
    op.drop_table("job_scan_matches")
    op.drop_table("job_scans")
    op.drop_table("job_search_profiles")
