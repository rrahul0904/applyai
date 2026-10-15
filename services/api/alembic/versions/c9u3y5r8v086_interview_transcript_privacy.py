"""Extend canonical mock interviews with consent, retention and transcript segments.

Revision ID: c9u3y5r8v086
Revises: b8t2x4q7u975
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c9u3y5r8v086"
down_revision = "b8t2x4q7u975"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mock_interview_sessions", sa.Column("transcript_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_interview_sessions", sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_interview_sessions", sa.Column("provenance_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_table(
        "interview_transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("interview_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mock_interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_turns.id", ondelete="CASCADE"), nullable=True),
        sa.Column("client_segment_id", sa.String(120), nullable=False),
        sa.Column("speaker", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("interview_session_id", "client_segment_id", name="uq_interview_segment_client_id"),
    )
    op.create_index("ix_interview_segments_session_created", "interview_transcript_segments", ["interview_session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_interview_segments_session_created", table_name="interview_transcript_segments")
    op.drop_table("interview_transcript_segments")
    op.drop_column("mock_interview_sessions", "provenance_json")
    op.drop_column("mock_interview_sessions", "retention_expires_at")
    op.drop_column("mock_interview_sessions", "transcript_consent_at")
