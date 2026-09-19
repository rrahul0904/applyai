"""add Hack2Hire company question-bank metadata

Revision ID: w3o7s9l2p420
Revises: v2n6r8k1o319
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "w3o7s9l2p420"
down_revision: str | None = "v2n6r8k1o319"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HACK2HIRE_URL = "https://www.hack2hire.com/question-bank/companies/openai/coding-questions"
TOPIC_ID = "46f98f6a-e649-4f1c-a6e3-b0183d217a02"


def upgrade() -> None:
    op.add_column(
        "interview_intelligence_questions",
        sa.Column(
            "stages",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_index(
        "ix_interview_intelligence_questions_stages",
        "interview_intelligence_questions",
        ["stages"],
        postgresql_using="gin",
    )
    op.alter_column("interview_intelligence_questions", "stages", server_default=None)

    op.execute(
        sa.text(
            f"""
            UPDATE reverse_engineering_topics
            SET
                source_url = '{HACK2HIRE_URL}',
                source_type = 'PUBLIC_PRODUCT_RESEARCH',
                evidence_urls = '[
                  "https://github.com/rrahul0904/applyai/pull/41",
                  "{HACK2HIRE_URL}"
                ]'::jsonb,
                status = 'INTEGRATED',
                metadata_json = COALESCE(metadata_json, '{{}}'::jsonb)
                  || '{{
                    "company_question_bank_filters": true,
                    "interview_stage_filter": true,
                    "freshness_sort": true,
                    "per_question_progress": true,
                    "source_reviewed_at": "2026-09-19"
                  }}'::jsonb
            WHERE id = '{TOPIC_ID}'::uuid
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE reverse_engineering_topics
            SET
                source_url = NULL,
                source_type = 'INTERNAL_RESEARCH_SUMMARY',
                evidence_urls = '["https://github.com/rrahul0904/applyai/pull/41"]'::jsonb,
                metadata_json = (COALESCE(metadata_json, '{{}}'::jsonb)
                  - 'company_question_bank_filters'
                  - 'interview_stage_filter'
                  - 'freshness_sort'
                  - 'per_question_progress'
                  - 'source_reviewed_at')
            WHERE id = '{TOPIC_ID}'::uuid
            """
        )
    )
    op.drop_index(
        "ix_interview_intelligence_questions_stages",
        table_name="interview_intelligence_questions",
    )
    op.drop_column("interview_intelligence_questions", "stages")
