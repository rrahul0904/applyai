"""add consolidated interview intelligence

Revision ID: s9k3o5h8l086
Revises: r8j2n4g7k975
Create Date: 2026-09-17
"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s9k3o5h8l086"
down_revision: str | None = "r8j2n4g7k975"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "interview_intelligence_workspaces",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_phase_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("interview_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interviewer_name", sa.String(240), nullable=True),
        sa.Column("interviewer_title", sa.String(240), nullable=True),
        sa.Column("interviewer_url", sa.Text(), nullable=True),
        sa.Column("lifecycle_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("readiness_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("podcast_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("research_sources_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="READY"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "job_id", name="uq_interview_intelligence_workspace_user_job"),
    )
    op.create_index("ix_interview_intelligence_workspaces_user_id", "interview_intelligence_workspaces", ["user_id"])
    op.create_index("ix_interview_intelligence_workspaces_job_id", "interview_intelligence_workspaces", ["job_id"])
    op.create_index("ix_interview_intelligence_workspace_user_updated", "interview_intelligence_workspaces", ["user_id", "updated_at"])

    op.create_table(
        "interview_stories",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("categories", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("task", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("metrics", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skills", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_fact_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_stories_user_id", "interview_stories", ["user_id"])
    op.create_index("ix_interview_stories_user_updated", "interview_stories", ["user_id", "updated_at"])

    questions = op.create_table(
        "interview_intelligence_questions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(240), nullable=False, unique=True),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("track", sa.String(48), nullable=False),
        sa.Column("difficulty", sa.String(24), nullable=False, server_default="MEDIUM"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("baseline_company_labels", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("company_labels", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skills", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("patterns", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("hints", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("follow_ups", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("solution_outline", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("baseline_frequency_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frequency_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_intelligence_questions_slug", "interview_intelligence_questions", ["slug"], unique=True)
    op.create_index("ix_interview_intelligence_questions_track_published", "interview_intelligence_questions", ["track", "published"])
    op.create_index("ix_interview_intelligence_questions_frequency", "interview_intelligence_questions", ["frequency_score"])
    op.create_index("ix_interview_intelligence_questions_last_reported", "interview_intelligence_questions", ["last_reported_at"])

    op.create_table(
        "interview_intelligence_reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("contributor_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=False, server_default="USER_SUBMISSION"),
        sa.Column("source_reference", sa.String(320), nullable=True),
        sa.Column("company_label", sa.String(240), nullable=True),
        sa.Column("role", sa.String(240), nullable=True),
        sa.Column("interview_stage", sa.String(120), nullable=True),
        sa.Column("title", sa.String(320), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("moderation_status", sa.String(48), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_intelligence_reports_contributor_user_id", "interview_intelligence_reports", ["contributor_user_id"])
    op.create_index("ix_interview_intelligence_reports_fingerprint", "interview_intelligence_reports", ["fingerprint"], unique=True)
    op.create_index("ix_interview_intelligence_reports_status_created", "interview_intelligence_reports", ["moderation_status", "created_at"])
    op.create_index("ix_interview_intelligence_reports_company_reported", "interview_intelligence_reports", ["company_label", "reported_at"])

    op.create_table(
        "interview_question_evidence",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("question_id", UUID, sa.ForeignKey("interview_intelligence_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", UUID, sa.ForeignKey("interview_intelligence_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("evidence_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("question_id", "report_id", name="uq_interview_question_evidence_pair"),
    )
    op.create_index("ix_interview_question_evidence_question_id", "interview_question_evidence", ["question_id"])
    op.create_index("ix_interview_question_evidence_report_id", "interview_question_evidence", ["report_id"])

    op.create_table(
        "interview_question_attempts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", UUID, sa.ForeignKey("interview_intelligence_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("code_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_question_attempts_user_id", "interview_question_attempts", ["user_id"])
    op.create_index("ix_interview_question_attempts_question_id", "interview_question_attempts", ["question_id"])
    op.create_index("ix_interview_question_attempts_job_id", "interview_question_attempts", ["job_id"])
    op.create_index("ix_interview_question_attempts_user_question", "interview_question_attempts", ["user_id", "question_id", "created_at"])
    op.create_index("ix_interview_question_attempts_user_job", "interview_question_attempts", ["user_id", "job_id", "created_at"])

    op.create_table(
        "interview_community_posts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_label", sa.String(240), nullable=True),
        sa.Column("category", sa.String(48), nullable=False, server_default="INTERVIEW_EXPERIENCE"),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("replies_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("reaction_user_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("moderation_status", sa.String(48), nullable=False, server_default="PUBLISHED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_community_posts_user_id", "interview_community_posts", ["user_id"])
    op.create_index("ix_interview_community_posts_created", "interview_community_posts", ["created_at"])
    op.create_index("ix_interview_community_posts_company_category", "interview_community_posts", ["company_label", "category"])

    for table in (
        "interview_intelligence_workspaces",
        "interview_stories",
        "interview_intelligence_questions",
        "interview_intelligence_reports",
        "interview_question_evidence",
        "interview_question_attempts",
        "interview_community_posts",
    ):
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))

    seed = [
        ("system-design-scale", "Design a resilient high-scale service", "SYSTEM_DESIGN", "HARD", ["architecture", "reliability"], ["capacity planning", "failure modes"]),
        ("sql-product-funnel", "Analyze a product conversion funnel in SQL", "SQL", "MEDIUM", ["sql", "analytics"], ["window functions", "data quality"]),
        ("coding-deduplicate-stream", "Deduplicate a high-volume event stream", "CODING", "MEDIUM", ["algorithms", "streaming"], ["hashing", "time complexity"]),
        ("ml-system-retrieval", "Design an ML retrieval and ranking system", "ML_SYSTEM_DESIGN", "HARD", ["machine learning", "ranking"], ["retrieval", "evaluation"]),
        ("ood-scheduler", "Model a production job scheduler", "OOD", "MEDIUM", ["object oriented design", "scheduling"], ["interfaces", "state"]),
        ("behavioral-stakeholder", "Influence a difficult stakeholder with evidence", "BEHAVIORAL", "MEDIUM", ["communication", "leadership"], ["STAR", "metrics"]),
        ("system-design-observability", "Design observability for a distributed platform", "SYSTEM_DESIGN", "MEDIUM", ["observability", "distributed systems"], ["SLO", "tracing"]),
        ("sql-retention", "Compute cohort retention with messy event data", "SQL", "HARD", ["sql", "data modeling"], ["cohorts", "null handling"]),
        ("coding-rate-limiter", "Implement a rate limiter", "CODING", "MEDIUM", ["algorithms", "systems"], ["token bucket", "concurrency"]),
        ("behavioral-failure", "Tell me about a failure and what changed afterward", "BEHAVIORAL", "EASY", ["ownership", "learning"], ["STAR", "reflection"]),
        ("ml-system-monitoring", "Monitor model quality after deployment", "ML_SYSTEM_DESIGN", "MEDIUM", ["machine learning", "observability"], ["drift", "evaluation"]),
        ("ood-notification", "Design a multi-channel notification service", "OOD", "MEDIUM", ["object oriented design", "messaging"], ["strategy pattern", "retries"]),
    ]
    rows = []
    for slug, title, track, difficulty, skills, patterns in seed:
        rows.append({
            "id": uuid.uuid4(),
            "slug": slug,
            "title": title,
            "track": track,
            "difficulty": difficulty,
            "summary": f"Clean-room {track.replace('_', ' ').title()} practice focused on reasoning, evidence, trade-offs and verification.",
            "prompt": title + ". Explain assumptions, trade-offs, verification, failure modes, and how you would measure success.",
            "baseline_company_labels": [],
            "company_labels": [],
            "skills": skills,
            "patterns": patterns,
            "hints": ["Clarify requirements and assumptions first.", "Name the core trade-off before proposing the implementation.", "Finish with verification, failure modes and measurable success criteria."],
            "follow_ups": ["What changes at 10x scale?", "What would you monitor in production?"],
            "solution_outline": ["Clarify", "Model", "Evaluate trade-offs", "Verify", "Operate"],
            "baseline_frequency_score": 25,
            "frequency_score": 25,
            "confidence": 30,
            "report_count": 0,
            "last_reported_at": None,
            "published": True,
        })
    op.bulk_insert(questions, rows)


def downgrade() -> None:
    for table in (
        "interview_community_posts",
        "interview_question_attempts",
        "interview_question_evidence",
        "interview_intelligence_reports",
        "interview_intelligence_questions",
        "interview_stories",
        "interview_intelligence_workspaces",
    ):
        op.drop_table(table)
