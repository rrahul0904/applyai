"""add ApplyAI reverse-engineering fit registry and AI evaluation receipts

Revision ID: r8j2n4g7k975
Revises: q7i1m3f6j864
Create Date: 2026-09-17
"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "r8j2n4g7k975"
down_revision: str | None = "q7i1m3f6j864"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    topics = op.create_table(
        "reverse_engineering_topics",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=False, server_default="PUBLIC_RESEARCH"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("applyai_fit", sa.String(32), nullable=False),
        sa.Column("fit_scope", sa.String(16), nullable=False),
        sa.Column("destination", sa.String(80), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("classifier_version", sa.String(32), nullable=False),
        sa.Column("classification_source", sa.String(16), nullable=False, server_default="AUTO"),
        sa.Column(
            "candidate_journey_stages",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "qualifying_capabilities",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "excluded_capabilities",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "evidence_urls",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="RESEARCHED"),
        sa.Column("implementation_target", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.UniqueConstraint("source_url", name="uq_reverse_engineering_topics_source_url"),
    )
    op.create_index(
        "ix_reverse_engineering_topics_fit_status",
        "reverse_engineering_topics",
        ["applyai_fit", "status"],
    )

    op.create_table(
        "ai_evaluation_receipts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_name", sa.String(160), nullable=False),
        sa.Column("subject_version", sa.String(80), nullable=False),
        sa.Column("content_digest", sa.String(71), nullable=False),
        sa.Column("dataset_version", sa.String(120), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("release_gate", sa.String(16), nullable=False),
        sa.Column("execution_status", sa.String(16), nullable=False),
        sa.Column("expected_rows", sa.Integer(), nullable=False),
        sa.Column("scored_rows", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("ties", sa.Integer(), nullable=False),
        sa.Column("net_lift", sa.Numeric(8, 5), nullable=False),
        sa.Column("sign_p", sa.Numeric(8, 5), nullable=False),
        sa.Column("trigger_precision", sa.Numeric(8, 5), nullable=True),
        sa.Column("trigger_recall", sa.Numeric(8, 5), nullable=True),
        sa.Column("baseline_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("candidate_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("cost_delta_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("baseline_duration_ms", sa.Numeric(14, 3), nullable=True),
        sa.Column("candidate_duration_ms", sa.Numeric(14, 3), nullable=True),
        sa.Column("duration_delta_ms", sa.Numeric(14, 3), nullable=True),
        sa.Column("receipt_digest", sa.String(71), nullable=False),
        sa.Column("receipt_json", JSONB, nullable=False),
        sa.Column("provenance_json", JSONB, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("receipt_digest", name="uq_ai_evaluation_receipts_digest"),
    )
    op.create_index(
        "ix_ai_evaluation_receipts_subject",
        "ai_evaluation_receipts",
        ["subject_type", "subject_name", "subject_version", "created_at"],
    )
    op.create_index(
        "ix_ai_evaluation_receipts_gate_verdict",
        "ai_evaluation_receipts",
        ["release_gate", "verdict"],
    )

    op.bulk_insert(
        topics,
        [
            {
                "id": uuid.UUID("70ad9bc8-7c38-47fb-b0b4-33ef84a50a17"),
                "title": "Terum Skills / Claude Skills Evaluation",
                "source_url": "https://www.reddit.com/r/claudeskills/s/Aeu7i3iWZj",
                "source_type": "REDDIT_GITHUB",
                "summary": (
                    "Local-first skill evaluation and team distribution using baseline, candidate, "
                    "and incumbent runs, content-addressed receipts, trigger metrics, and shareable scorecards."
                ),
                "applyai_fit": "INFRASTRUCTURE",
                "fit_scope": "PARTIAL",
                "destination": "platform-infrastructure",
                "rationale": (
                    "Reuse A/B evaluation, regression detection, immutable receipts, provenance, trigger "
                    "precision/recall, cost and latency measurements, and release gates for ApplyAI agents. "
                    "Keep the generic Claude skill marketplace, desktop skill library, and general-purpose "
                    "team distribution outside ApplyAI."
                ),
                "classifier_version": "2026-09-17.1",
                "classification_source": "MANUAL",
                "candidate_journey_stages": ["MEASURE_READINESS"],
                "qualifying_capabilities": [
                    "agent/skill A/B evaluation",
                    "baseline-vs-candidate testing",
                    "regression detection",
                    "immutable evaluation receipts",
                    "provenance",
                    "trigger precision/recall",
                    "cost/latency measurements",
                    "PASS/NEUTRAL/FAIL release gates",
                ],
                "excluded_capabilities": [
                    "generic Claude skill marketplace",
                    "generic desktop skill library",
                    "general-purpose team skill distribution",
                ],
                "evidence_urls": ["https://github.com/ryanliu-terum/terum-skills"],
                "status": "INTEGRATED",
                "implementation_target": "ApplyAI agent and workflow evaluation gates",
                "metadata_json": {"seed": "2026-09-17-terum-reverse-engineering"},
            }
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_evaluation_receipts_gate_verdict",
        table_name="ai_evaluation_receipts",
    )
    op.drop_index(
        "ix_ai_evaluation_receipts_subject",
        table_name="ai_evaluation_receipts",
    )
    op.drop_table("ai_evaluation_receipts")
    op.drop_index(
        "ix_reverse_engineering_topics_fit_status",
        table_name="reverse_engineering_topics",
    )
    op.drop_table("reverse_engineering_topics")
