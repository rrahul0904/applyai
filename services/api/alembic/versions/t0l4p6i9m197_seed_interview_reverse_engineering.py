"""seed consolidated interview reverse-engineering decisions

Revision ID: t0l4p6i9m197
Revises: s9k3o5h8l086
Create Date: 2026-09-17
"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "t0l4p6i9m197"
down_revision: str | None = "s9k3o5h8l086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    topics = sa.table(
        "reverse_engineering_topics",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("title", sa.String()),
        sa.column("source_url", sa.Text()),
        sa.column("source_type", sa.String()),
        sa.column("summary", sa.Text()),
        sa.column("applyai_fit", sa.String()),
        sa.column("fit_scope", sa.String()),
        sa.column("destination", sa.String()),
        sa.column("rationale", sa.Text()),
        sa.column("classifier_version", sa.String()),
        sa.column("classification_source", sa.String()),
        sa.column("candidate_journey_stages", postgresql.JSONB()),
        sa.column("qualifying_capabilities", postgresql.JSONB()),
        sa.column("excluded_capabilities", postgresql.JSONB()),
        sa.column("evidence_urls", postgresql.JSONB()),
        sa.column("status", sa.String()),
        sa.column("implementation_target", sa.Text()),
        sa.column("metadata_json", postgresql.JSONB()),
    )
    op.bulk_insert(
        topics,
        [
            {
                "id": uuid.UUID("46f98f6a-e649-4f1c-a6e3-b0183d217a01"),
                "title": "Hirecast-style Interview Lifecycle",
                "source_url": None,
                "source_type": "INTERNAL_RESEARCH_SUMMARY",
                "summary": "Job-specific four-phase interview lifecycle with grounded prep, flashcards, notes, retrospectives, readiness, STAR stories and audio-friendly briefings.",
                "applyai_fit": "PREPARE",
                "fit_scope": "FULL",
                "destination": "prepare",
                "rationale": "The qualifying behavior directly strengthens interview preparation, practice, readiness and evidence reuse. It is implemented as an additive intelligence layer over the existing ApplyAI Prepare stack.",
                "classifier_version": "2026-09-17.1",
                "classification_source": "MANUAL",
                "candidate_journey_stages": ["PREPARE_FOR_INTERVIEWS", "PRACTICE_MOCK", "MEASURE_READINESS", "MANAGE_CAREER_INTELLIGENCE"],
                "qualifying_capabilities": ["four-phase interview lifecycle", "flashcards", "private notes", "current-phase retrospectives", "carry-forward actions", "STAR story bank", "podcast briefing scripts", "readiness evidence"],
                "excluded_capabilities": ["unverified interviewer claims", "fake hosted audio", "broken RSS without real audio", "proprietary prompts or source material"],
                "evidence_urls": ["https://github.com/rrahul0904/applyai/pull/39"],
                "status": "INTEGRATED",
                "implementation_target": "ApplyAI Prepare job workspace and Interview Intelligence lifecycle",
                "metadata_json": {"supersedes_experimental_pr": 39, "clean_room": True},
            },
            {
                "id": uuid.UUID("46f98f6a-e649-4f1c-a6e3-b0183d217a02"),
                "title": "Hack2Hire-style Interview Intelligence",
                "source_url": None,
                "source_type": "INTERNAL_RESEARCH_SUMMARY",
                "summary": "Clean-room interview question intelligence with track filters, company evidence, durable practice, staged hints, candidate reports, moderation, provenance and community.",
                "applyai_fit": "PREPARE",
                "fit_scope": "PARTIAL",
                "destination": "prepare",
                "rationale": "Question/company intelligence and evidence-backed coaching strengthen ApplyAI Prepare. Arbitrary execution and unrelated referral-growth mechanics remain outside the core product boundary.",
                "classifier_version": "2026-09-17.1",
                "classification_source": "MANUAL",
                "candidate_journey_stages": ["UNDERSTAND_FIT", "PREPARE_FOR_INTERVIEWS", "PRACTICE_MOCK", "MEASURE_READINESS", "MANAGE_CAREER_INTELLIGENCE"],
                "qualifying_capabilities": ["question bank", "company collections", "frequency/recency/confidence", "durable attempts", "staged coaching", "candidate reports", "operator moderation", "reversible evidence aggregates", "candidate community"],
                "excluded_capabilities": ["embedded arbitrary code execution", "embedded SQL execution", "referral-credit growth mechanics", "proprietary question banks"],
                "evidence_urls": ["https://github.com/rrahul0904/applyai/pull/41"],
                "status": "INTEGRATED",
                "implementation_target": "ApplyAI Interview Intelligence hub, Prepare lifecycle and operator evidence workspace",
                "metadata_json": {"supersedes_experimental_pr": 41, "clean_room": True, "execution_boundary": "external-isolated-integration"},
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM reverse_engineering_topics WHERE id IN "
            "('46f98f6a-e649-4f1c-a6e3-b0183d217a01', '46f98f6a-e649-4f1c-a6e3-b0183d217a02')"
        )
    )
