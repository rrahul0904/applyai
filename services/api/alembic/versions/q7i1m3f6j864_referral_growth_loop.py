"""add referral growth loop

Revision ID: q7i1m3f6j864
Revises: p6h0l2e5i753
Create Date: 2026-09-12
"""

from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "q7i1m3f6j864"
down_revision: str | None = "p6h0l2e5i753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "referral_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_referral_codes_user_id", "referral_codes", ["user_id"])

    op.create_table(
        "referral_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("referral_code_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("referral_codes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referrer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referred_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("qualified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_referral_events_referral_code_id", "referral_events", ["referral_code_id"])
    op.create_index("ix_referral_events_referrer_user_id", "referral_events", ["referrer_user_id"])
    op.create_index("ix_referral_events_referred_user_id", "referral_events", ["referred_user_id"])

    op.create_table(
        "referral_credit_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("referral_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("referral_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("beneficiary_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_type", sa.String(32), nullable=False, server_default="REFERRER_CREDIT"),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="AVAILABLE"),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("referral_event_id", "entry_type", "beneficiary_user_id"),
    )
    op.create_index("ix_referral_credit_ledger_event", "referral_credit_ledger", ["referral_event_id"])
    op.create_index("ix_referral_credit_ledger_beneficiary", "referral_credit_ledger", ["beneficiary_user_id"])


def downgrade() -> None:
    op.drop_table("referral_credit_ledger")
    op.drop_table("referral_events")
    op.drop_table("referral_codes")
