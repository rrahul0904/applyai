"""platform completion domains

Revision ID: e5c9a1b4d642
Revises: d4b8f0a2c531
Create Date: 2026-08-07 00:04:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5c9a1b4d642"
down_revision: Union[str, None] = "d4b8f0a2c531"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("query", JSONB, nullable=False, server_default="{}"),
        sa.Column("alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("minimum_match_score", sa.Integer(), nullable=False, server_default="70"),
        *timestamps(),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("job_match_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("application_reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interview_reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("recruiter_followup_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("quiet_hours", JSONB, nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "candidate_analytics_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(48)),
        sa.Column("entity_id", sa.String(128)),
        sa.Column("metadata_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_analytics_events_user_id", "candidate_analytics_events", ["user_id"])
    op.create_index("ix_candidate_analytics_user_type_time", "candidate_analytics_events", ["user_id", "event_type", "occurred_at"])

    op.create_table(
        "candidate_contacts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("company", sa.String(240)),
        sa.Column("title", sa.String(240)),
        sa.Column("email", sa.String(320)),
        sa.Column("linkedin_url", sa.Text()),
        sa.Column("relationship", sa.String(80)),
        sa.Column("notes", sa.Text()),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True)),
        sa.Column("followup_at", sa.DateTime(timezone=True)),
        *timestamps(),
    )
    op.create_index("ix_candidate_contacts_user_id", "candidate_contacts", ["user_id"])
    op.create_index("ix_candidate_contacts_user_followup", "candidate_contacts", ["user_id", "followup_at"])

    op.create_table(
        "resume_studio_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("base_resume_version_id", UUID, sa.ForeignKey("resume_versions.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("content", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *timestamps(),
    )
    op.create_index("ix_resume_studio_documents_user_id", "resume_studio_documents", ["user_id"])
    op.create_index("ix_resume_studio_user_job", "resume_studio_documents", ["user_id", "job_id"])

    op.create_table(
        "interview_practice_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(48), nullable=False, server_default="BEHAVIORAL"),
        sa.Column("responses", JSONB, nullable=False, server_default="[]"),
        sa.Column("feedback", JSONB, nullable=False, server_default="{}"),
        sa.Column("score", sa.Integer()),
        *timestamps(),
    )
    op.create_index("ix_interview_practice_sessions_user_id", "interview_practice_sessions", ["user_id"])
    op.create_index("ix_interview_practice_user_job", "interview_practice_sessions", ["user_id", "job_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("plan", sa.String(48), nullable=False, server_default="FREE"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("provider", sa.String(48), nullable=False, server_default="INTERNAL"),
        sa.Column("provider_customer_id", sa.String(255)),
        sa.Column("provider_subscription_id", sa.String(255)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("usage", JSONB, nullable=False, server_default="{}"),
        *timestamps(),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.create_table(
        "billing_ledger_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("provider_ref", sa.String(255)),
        sa.Column("metadata_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_billing_ledger_events_user_id", "billing_ledger_events", ["user_id"])

    op.create_table(
        "application_submission_requests",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID, sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("mode", sa.String(48), nullable=False, server_default="EXTERNAL_HANDOFF"),
        sa.Column("provider", sa.String(80), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(48), nullable=False, server_default="DRAFT"),
        sa.Column("target_url", sa.Text()),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        *timestamps(),
        sa.UniqueConstraint("application_id", "attempt_number"),
    )
    op.create_index("ix_application_submission_requests_user_id", "application_submission_requests", ["user_id"])
    op.create_index("ix_application_submission_requests_application_id", "application_submission_requests", ["application_id"])

    op.create_table(
        "employer_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("employer_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canonical_job_id", UUID, sa.ForeignKey("jobs.id", ondelete="SET NULL"), unique=True),
        sa.Column("title", sa.String(280), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location_text", sa.String(280)),
        sa.Column("work_mode", sa.String(32), nullable=False, server_default="ONSITE"),
        sa.Column("employment_type", sa.String(48)),
        sa.Column("seniority", sa.String(48)),
        sa.Column("compensation_min", sa.Integer()),
        sa.Column("compensation_max", sa.Integer()),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        *timestamps(),
    )
    op.create_index("ix_employer_jobs_organization_id", "employer_jobs", ["organization_id"])
    op.create_index("ix_employer_jobs_org_status", "employer_jobs", ["organization_id", "status"])

    op.create_table(
        "employer_applicants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("employer_job_id", UUID, sa.ForeignKey("employer_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID, sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(48), nullable=False, server_default="NEW"),
        sa.Column("rating", sa.Integer()),
        sa.Column("notes", JSONB, nullable=False, server_default="[]"),
        *timestamps(),
        sa.UniqueConstraint("employer_job_id", "application_id"),
    )
    op.create_index("ix_employer_applicants_employer_job_id", "employer_applicants", ["employer_job_id"])
    op.create_index("ix_employer_applicants_application_id", "employer_applicants", ["application_id"])


def downgrade() -> None:
    for table in [
        "employer_applicants",
        "employer_jobs",
        "application_submission_requests",
        "billing_ledger_events",
        "subscriptions",
        "interview_practice_sessions",
        "resume_studio_documents",
        "candidate_contacts",
        "candidate_analytics_events",
        "notification_preferences",
        "saved_searches",
    ]:
        op.drop_table(table)
