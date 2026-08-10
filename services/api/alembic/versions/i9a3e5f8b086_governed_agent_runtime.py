"""governed agent runtime

Revision ID: i9a3e5f8b086
Revises: h8f2d4e7a975
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "i9a3e5f8b086"
down_revision: str | None = "h8f2d4e7a975"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.Column("trigger_type", sa.String(length=48), nullable=False),
        sa.Column("trigger_id", sa.String(length=255), nullable=True),
        sa.Column("workflow_type", sa.String(length=80), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("execution_class", sa.String(length=16), nullable=False),
        sa.Column("queue_class", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=512), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current_step", sa.String(length=120), nullable=True),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("provider", sa.String(length=48), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("schema_version", sa.String(length=80), nullable=True),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_runs_idempotency_key"),
    )
    op.create_index("ix_agent_runs_candidate_id", "agent_runs", ["candidate_id"])
    op.create_index("ix_agent_runs_job_id", "agent_runs", ["job_id"])
    op.create_index("ix_agent_runs_agent_name", "agent_runs", ["agent_name"])
    op.create_index("ix_agent_runs_workflow_type", "agent_runs", ["workflow_type"])
    op.create_index("ix_agent_runs_workflow_id", "agent_runs", ["workflow_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_lease_expires_at", "agent_runs", ["lease_expires_at"])
    op.create_index("ix_agent_runs_claim", "agent_runs", ["status", "priority", "created_at"])
    op.create_index("ix_agent_runs_candidate_created", "agent_runs", ["candidate_id", "created_at"])
    op.create_index("ix_agent_runs_agent_status", "agent_runs", ["agent_name", "status", "created_at"])

    op.create_table(
        "agent_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=120), nullable=False),
        sa.Column("step_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("input_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.String(length=48), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "step_name", "attempt", name="uq_agent_steps_run_name_attempt"),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.create_index("ix_agent_steps_run_position", "agent_steps", ["run_id", "position"])

    op.create_table(
        "agent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])
    op.create_index("ix_agent_events_candidate_id", "agent_events", ["candidate_id"])
    op.create_index("ix_agent_events_event_type", "agent_events", ["event_type"])
    op.create_index("ix_agent_events_candidate_created", "agent_events", ["candidate_id", "created_at"])

    op.create_table(
        "agent_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("parent_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supersedes_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("schema_version", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_artifact_id"], ["agent_artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_artifact_id"], ["agent_artifacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "artifact_type", "version", name="uq_agent_artifacts_run_type_version"),
    )
    op.create_index("ix_agent_artifacts_run_id", "agent_artifacts", ["run_id"])
    op.create_index("ix_agent_artifacts_candidate_id", "agent_artifacts", ["candidate_id"])
    op.create_index("ix_agent_artifacts_job_id", "agent_artifacts", ["job_id"])
    op.create_index("ix_agent_artifacts_artifact_type", "agent_artifacts", ["artifact_type"])
    op.create_index("ix_agent_artifacts_candidate_job_type", "agent_artifacts", ["candidate_id", "job_id", "artifact_type"])

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("tool_version", sa.String(length=32), nullable=False),
        sa.Column("execution_class", sa.String(length=16), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["agent_steps.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tool_calls_run_id", "agent_tool_calls", ["run_id"])
    op.create_index("ix_agent_tool_calls_candidate_id", "agent_tool_calls", ["candidate_id"])
    op.create_index("ix_agent_tool_calls_run_created", "agent_tool_calls", ["run_id", "created_at"])

    op.create_table(
        "agent_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("policy_version", sa.String(length=48), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["artifact_id"], ["agent_artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_approvals_run_id", "agent_approvals", ["run_id"])
    op.create_index("ix_agent_approvals_candidate_id", "agent_approvals", ["candidate_id"])
    op.create_index("ix_agent_approvals_status", "agent_approvals", ["status"])
    op.create_index("ix_agent_approvals_candidate_status", "agent_approvals", ["candidate_id", "status", "requested_at"])

    op.create_table(
        "agent_cost_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=48), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_cost_events_run_id", "agent_cost_events", ["run_id"])
    op.create_index("ix_agent_cost_events_candidate_id", "agent_cost_events", ["candidate_id"])
    op.create_index("ix_agent_cost_events_agent_name", "agent_cost_events", ["agent_name"])
    op.create_index("ix_agent_cost_events_candidate_created", "agent_cost_events", ["candidate_id", "created_at"])

    op.create_table(
        "agent_runtime_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.Column("enabled_override", sa.Boolean(), nullable=True),
        sa.Column("max_cost_usd_override", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_name", "agent_version", name="uq_agent_runtime_policy_definition"),
    )
    op.create_index("ix_agent_runtime_policies_agent_name", "agent_runtime_policies", ["agent_name"])


def downgrade() -> None:
    op.drop_index("ix_agent_runtime_policies_agent_name", table_name="agent_runtime_policies")
    op.drop_table("agent_runtime_policies")
    op.drop_index("ix_agent_cost_events_candidate_created", table_name="agent_cost_events")
    op.drop_index("ix_agent_cost_events_agent_name", table_name="agent_cost_events")
    op.drop_index("ix_agent_cost_events_candidate_id", table_name="agent_cost_events")
    op.drop_index("ix_agent_cost_events_run_id", table_name="agent_cost_events")
    op.drop_table("agent_cost_events")
    op.drop_index("ix_agent_approvals_candidate_status", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_status", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_candidate_id", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_run_id", table_name="agent_approvals")
    op.drop_table("agent_approvals")
    op.drop_index("ix_agent_tool_calls_run_created", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_candidate_id", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_run_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")
    op.drop_index("ix_agent_artifacts_candidate_job_type", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_artifact_type", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_job_id", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_candidate_id", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_run_id", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
    op.drop_index("ix_agent_events_candidate_created", table_name="agent_events")
    op.drop_index("ix_agent_events_event_type", table_name="agent_events")
    op.drop_index("ix_agent_events_candidate_id", table_name="agent_events")
    op.drop_index("ix_agent_events_run_id", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("ix_agent_steps_run_position", table_name="agent_steps")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_agent_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_candidate_created", table_name="agent_runs")
    op.drop_index("ix_agent_runs_claim", table_name="agent_runs")
    op.drop_index("ix_agent_runs_lease_expires_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_workflow_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_workflow_type", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_name", table_name="agent_runs")
    op.drop_index("ix_agent_runs_job_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_candidate_id", table_name="agent_runs")
    op.drop_table("agent_runs")
