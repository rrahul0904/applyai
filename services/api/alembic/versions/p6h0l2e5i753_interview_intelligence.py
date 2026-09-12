"""add interview intelligence platform

Revision ID: p6h0l2e5i753
Revises: o5g9k1d4h642
Create Date: 2026-09-12
"""

from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "p6h0l2e5i753"
down_revision: str | None = "o5g9k1d4h642"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_intelligence_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(240), nullable=False, unique=True),
        sa.Column("title", sa.String(320), nullable=False), sa.Column("track", sa.String(48), nullable=False),
        sa.Column("difficulty", sa.String(24), nullable=False, server_default="MEDIUM"),
        sa.Column("summary", sa.Text(), nullable=False), sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("company_labels", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skills", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("patterns", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("hints", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("follow_ups", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("solution_outline", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("test_cases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("starter_code", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("frequency_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reported_at", sa.DateTime(timezone=True)),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_questions_track_published", "interview_intelligence_questions", ["track", "published"])
    op.create_index("ix_interview_questions_last_reported", "interview_intelligence_questions", ["last_reported_at"])
    op.create_index("ix_interview_questions_frequency", "interview_intelligence_questions", ["frequency_score"])

    op.create_table(
        "interview_intelligence_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contributor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("source_type", sa.String(48), nullable=False), sa.Column("source_url", sa.Text()), sa.Column("source_reference", sa.String(320)),
        sa.Column("company_label", sa.String(240)), sa.Column("role", sa.String(240)), sa.Column("interview_stage", sa.String(120)), sa.Column("title", sa.String(320)),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("license_status", sa.String(48), nullable=False, server_default="USER_SUBMITTED"),
        sa.Column("moderation_status", sa.String(48), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column("extraction_confidence", sa.Integer(), nullable=False, server_default="0"), sa.Column("reported_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_reports_status_created", "interview_intelligence_reports", ["moderation_status", "created_at"])
    op.create_index("ix_interview_reports_company_reported", "interview_intelligence_reports", ["company_label", "reported_at"])
    op.create_index("ix_interview_intelligence_reports_contributor_user_id", "interview_intelligence_reports", ["contributor_user_id"])

    op.create_table(
        "interview_question_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_intelligence_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_intelligence_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"), sa.Column("evidence_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("question_id", "report_id"),
    )
    op.create_index("ix_interview_question_evidence_question_id", "interview_question_evidence", ["question_id"])
    op.create_index("ix_interview_question_evidence_report_id", "interview_question_evidence", ["report_id"])

    op.create_table(
        "interview_intelligence_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_intelligence_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False, server_default="IN_PROGRESS"), sa.Column("language", sa.String(48)), sa.Column("answer", sa.Text()), sa.Column("code", sa.Text()),
        sa.Column("feedback", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("execution_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("score", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_attempts_user_question", "interview_intelligence_attempts", ["user_id", "question_id"])
    op.create_index("ix_interview_attempts_user_job", "interview_intelligence_attempts", ["user_id", "job_id"])
    op.create_index("ix_interview_intelligence_attempts_user_id", "interview_intelligence_attempts", ["user_id"])

    op.create_table(
        "interview_preparation_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("readiness_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strengths", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("gaps", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("actions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "job_id"),
    )
    op.create_index("ix_interview_preparation_plans_user_id", "interview_preparation_plans", ["user_id"])
    op.create_index("ix_interview_preparation_plans_job_id", "interview_preparation_plans", ["job_id"])

    op.create_table(
        "interview_community_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_label", sa.String(240)), sa.Column("category", sa.String(48), nullable=False, server_default="INTERVIEW_EXPERIENCE"), sa.Column("title", sa.String(320), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("moderation_status", sa.String(48), nullable=False, server_default="PUBLISHED"), sa.Column("reaction_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("reply_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_community_created", "interview_community_posts", ["created_at"])
    op.create_index("ix_interview_community_company_category", "interview_community_posts", ["company_label", "category"])
    op.create_index("ix_interview_community_posts_user_id", "interview_community_posts", ["user_id"])

    op.create_table(
        "interview_community_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_community_posts.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("moderation_status", sa.String(48), nullable=False, server_default="PUBLISHED"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_community_replies_post_id", "interview_community_replies", ["post_id"]); op.create_index("ix_interview_community_replies_user_id", "interview_community_replies", ["user_id"])

    op.create_table(
        "interview_community_reactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_community_posts.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reaction", sa.String(32), nullable=False, server_default="UPVOTE"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.UniqueConstraint("post_id", "user_id", "reaction"),
    )
    op.create_index("ix_interview_community_reactions_post_id", "interview_community_reactions", ["post_id"]); op.create_index("ix_interview_community_reactions_user_id", "interview_community_reactions", ["user_id"])

    question = sa.table("interview_intelligence_questions", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("slug", sa.String()), sa.column("title", sa.String()), sa.column("track", sa.String()), sa.column("difficulty", sa.String()), sa.column("summary", sa.Text()), sa.column("prompt", sa.Text()), sa.column("company_labels", postgresql.JSONB()), sa.column("skills", postgresql.JSONB()), sa.column("patterns", postgresql.JSONB()), sa.column("hints", postgresql.JSONB()), sa.column("follow_ups", postgresql.JSONB()), sa.column("solution_outline", postgresql.JSONB()), sa.column("test_cases", postgresql.JSONB()), sa.column("starter_code", postgresql.JSONB()), sa.column("frequency_score", sa.Integer()), sa.column("confidence", sa.Integer()), sa.column("report_count", sa.Integer()), sa.column("published", sa.Boolean()))
    op.bulk_insert(question, [
        {"id":"10000000-0000-0000-0000-000000000001","slug":"distributed-rate-limiter","title":"Design a distributed rate limiter","track":"SYSTEM_DESIGN","difficulty":"HARD","summary":"Design a low-latency multi-region rate-limiting service with tenant-specific policies and graceful degradation.","prompt":"Design a production rate limiter for a global API platform. Clarify scale, policy semantics, consistency, regional failure handling, observability, and abuse controls.","company_labels":["OpenAI","Stripe"],"skills":["distributed-systems","redis","consistency","observability"],"patterns":["token-bucket","regional-sharding"],"hints":["Separate policy storage from the request hot path.","Compare token bucket and sliding-window behavior under bursts.","State what happens when a region loses contact with the global control plane."],"follow_ups":["How would you prevent one tenant from causing hot-key pressure?","What metrics prove the limiter is healthy during a regional incident?"],"solution_outline":["Clarify requirements.","Choose a local fast path and synchronization model.","Design policy distribution and multi-region failover.","Add observability and abuse controls."],"test_cases":[],"starter_code":{},"frequency_score":92,"confidence":90,"report_count":0,"published":True},
        {"id":"10000000-0000-0000-0000-000000000002","slug":"streaming-top-k-window","title":"Maintain top-K events in a streaming window","track":"CODING","difficulty":"MEDIUM","summary":"Maintain the K most frequent event types over a moving window while keeping update and query costs bounded.","prompt":"Implement or describe a data structure that consumes events continuously and returns the current top-K event types for a moving window.","company_labels":["Snowflake","Databricks"],"skills":["heap","hash-map","streaming"],"patterns":["lazy-invalidation","frequency-map"],"hints":["Clarify whether the window is count-based or time-based.","Use a frequency map as the source of truth.","If using a heap, explain stale-entry cleanup."],"follow_ups":["How does this change for event time?","What if K changes at runtime?"],"solution_outline":["Define window semantics.","Track active counts.","Maintain top-K candidates.","Explain cleanup and complexity."],"test_cases":[{"input":{"events":["a","b","a","c","a","b"],"k":2},"expected":["a","b"]}],"starter_code":{"python":"def top_k(events, k):\n    pass\n"},"frequency_score":88,"confidence":90,"report_count":0,"published":True},
        {"id":"10000000-0000-0000-0000-000000000003","slug":"subscription-retention-cohorts","title":"Calculate subscription retention by cohort","track":"SQL","difficulty":"MEDIUM","summary":"Calculate M0-M6 retention for signup cohorts from subscription activity with multiple subscription periods per user.","prompt":"Using PostgreSQL, return monthly signup cohorts and retained-user percentages for months zero through six.","company_labels":["Stripe","Airbnb"],"skills":["sql","window-functions","cohort-analysis"],"patterns":["calendar-normalization","conditional-aggregation"],"hints":["Build one row per user for cohort assignment.","Normalize activity into distinct user-months.","Guard against duplicate subscription periods."],"follow_ups":["How would you handle reactivations?","How would you make this incremental?"],"solution_outline":["Derive signup cohort.","Normalize active months.","Compute month offsets.","Aggregate distinct retained users."],"test_cases":[],"starter_code":{"sql":"WITH cohorts AS (\n  -- your query\n)\nSELECT * FROM cohorts;\n"},"frequency_score":78,"confidence":86,"report_count":0,"published":True},
        {"id":"10000000-0000-0000-0000-000000000004","slug":"online-offline-feature-store","title":"Design an online and offline feature store","track":"ML_SYSTEM_DESIGN","difficulty":"HARD","summary":"Design feature computation and serving with point-in-time correctness for training and low-latency inference.","prompt":"Design a feature platform supporting batch and streaming computation, offline training datasets, and online serving without training-serving skew.","company_labels":["Uber","OpenAI"],"skills":["ml-platform","point-in-time-correctness","streaming","serving"],"patterns":["dual-store","event-time","materialization"],"hints":["Separate feature definitions from storage.","Explain how point-in-time joins prevent leakage.","Treat freshness and skew as observable SLOs."],"follow_ups":["How do you backfill a changed feature safely?","How do you version features used by deployed models?"],"solution_outline":["Define registry and ownership.","Design materialization.","Guarantee temporal correctness.","Add freshness and lineage."],"test_cases":[],"starter_code":{},"frequency_score":74,"confidence":84,"report_count":0,"published":True},
        {"id":"10000000-0000-0000-0000-000000000005","slug":"extensible-parking-garage","title":"Design an extensible parking garage","track":"OOD","difficulty":"MEDIUM","summary":"Model vehicle entry, spot allocation, tickets, pricing, and payment while keeping policies replaceable.","prompt":"Design the core objects and interactions for a multi-floor parking garage with vehicle types, allocation, dynamic pricing, tickets, and payment.","company_labels":["Amazon","Microsoft"],"skills":["object-modeling","solid","state-machines"],"patterns":["strategy","state"],"hints":["Identify stable domain boundaries before choosing patterns.","Do not make Garage responsible for everything.","Show how pricing changes without changing ticket logic."],"follow_ups":["How would reservations change the model?","How would allocation become concurrency-safe?"],"solution_outline":["Identify entities and invariants.","Separate policies.","Model ticket lifecycle.","Show extension points."],"test_cases":[],"starter_code":{},"frequency_score":66,"confidence":82,"report_count":0,"published":True},
        {"id":"10000000-0000-0000-0000-000000000006","slug":"incident-leadership-evidence","title":"Lead through an ambiguous production incident","track":"BEHAVIORAL","difficulty":"MEDIUM","summary":"Build an evidence-backed leadership story about an ambiguous incident, your direct decisions, and measurable result.","prompt":"Describe a production incident with incomplete information. Explain your responsibility, decisions, trade-offs, result, and what you changed afterward.","company_labels":["OpenAI","Meta","Google"],"skills":["leadership","incident-response","communication"],"patterns":["star","evidence-first"],"hints":["Separate your contribution from the team outcome.","Include the decision you made with incomplete information.","End with a measurable result and durable change."],"follow_ups":["What would you do differently now?","How did you keep stakeholders aligned?"],"solution_outline":["Situation and stakes.","Your responsibility.","Decision process.","Measured result.","Learning and durable change."],"test_cases":[],"starter_code":{},"frequency_score":80,"confidence":80,"report_count":0,"published":True},
    ])


def downgrade() -> None:
    op.drop_table("interview_community_reactions"); op.drop_table("interview_community_replies"); op.drop_table("interview_community_posts")
    op.drop_table("interview_preparation_plans"); op.drop_table("interview_intelligence_attempts"); op.drop_table("interview_question_evidence")
    op.drop_table("interview_intelligence_reports"); op.drop_table("interview_intelligence_questions")
