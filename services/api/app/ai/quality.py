from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.career_models import AIArtifact, AIJobRun, CandidateAIArtifactFeedback


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ai_quality_metrics(session: Session, *, window_hours: int = 24) -> dict:
    since = utcnow() - timedelta(hours=window_hours)

    run_rows = list(
        session.execute(
            select(
                AIJobRun.task_type,
                AIJobRun.provider,
                AIJobRun.model,
                AIJobRun.status,
                func.count(AIJobRun.id),
                func.avg(AIJobRun.latency_ms),
                func.coalesce(func.sum(AIJobRun.input_tokens), 0),
                func.coalesce(func.sum(AIJobRun.output_tokens), 0),
                func.coalesce(func.sum(AIJobRun.estimated_cost_usd), 0),
            )
            .where(AIJobRun.created_at >= since)
            .group_by(
                AIJobRun.task_type,
                AIJobRun.provider,
                AIJobRun.model,
                AIJobRun.status,
            )
            .order_by(AIJobRun.task_type, AIJobRun.provider, AIJobRun.model)
        )
    )

    status_counts: dict[str, int] = {}
    task_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    latency_values: list[tuple[float, int]] = []
    breakdown: list[dict] = []

    for (
        task_type,
        provider,
        model,
        status,
        count,
        average_latency_ms,
        input_tokens,
        output_tokens,
        estimated_cost,
    ) in run_rows:
        count_value = int(count or 0)
        status_counts[status] = status_counts.get(status, 0) + count_value
        task_counts[task_type] = task_counts.get(task_type, 0) + count_value
        provider_counts[provider] = provider_counts.get(provider, 0) + count_value
        total_input_tokens += int(input_tokens or 0)
        total_output_tokens += int(output_tokens or 0)
        total_cost += float(estimated_cost or 0)
        if average_latency_ms is not None:
            latency_values.append((float(average_latency_ms), count_value))
        breakdown.append(
            {
                "task_type": task_type,
                "provider": provider,
                "model": model,
                "status": status,
                "count": count_value,
                "average_latency_ms": (
                    round(float(average_latency_ms), 2)
                    if average_latency_ms is not None
                    else None
                ),
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
                "estimated_cost_usd": round(float(estimated_cost or 0), 6),
            }
        )

    total_runs = sum(status_counts.values())
    completed = status_counts.get("COMPLETED", 0)
    failed = status_counts.get("FAILED", 0)
    weighted_latency = (
        sum(latency * count for latency, count in latency_values)
        / sum(count for _, count in latency_values)
        if latency_values and sum(count for _, count in latency_values)
        else None
    )

    artifact_total, artifact_verified = session.execute(
        select(
            func.count(AIArtifact.id),
            func.count(AIArtifact.id).filter(AIArtifact.candidate_verified.is_(True)),
        ).where(AIArtifact.created_at >= since)
    ).one()

    feedback_rows = list(
        session.execute(
            select(
                CandidateAIArtifactFeedback.action,
                func.count(CandidateAIArtifactFeedback.id),
            )
            .where(CandidateAIArtifactFeedback.created_at >= since)
            .group_by(CandidateAIArtifactFeedback.action)
        )
    )
    feedback = {action: int(count) for action, count in feedback_rows}
    review_actions = sum(
        feedback.get(action, 0) for action in ("ACCEPTED", "EDITED", "REJECTED")
    )

    return {
        "window_hours": window_hours,
        "runs": {
            "total": total_runs,
            "completed": completed,
            "failed": failed,
            "queued_or_processing": max(0, total_runs - completed - failed),
            "success_rate": round(completed / total_runs, 4) if total_runs else None,
            "failure_rate": round(failed / total_runs, 4) if total_runs else None,
            "average_latency_ms": (
                round(weighted_latency, 2) if weighted_latency is not None else None
            ),
            "by_status": status_counts,
            "by_task": task_counts,
            "by_provider": provider_counts,
        },
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "estimated_cost_usd": round(total_cost, 6),
            "cost_per_completed_run_usd": (
                round(total_cost / completed, 6) if completed else None
            ),
        },
        "artifacts": {
            "total": int(artifact_total or 0),
            "candidate_verified": int(artifact_verified or 0),
            "candidate_verification_rate": (
                round(int(artifact_verified or 0) / int(artifact_total), 4)
                if artifact_total
                else None
            ),
        },
        "feedback": {
            **feedback,
            "review_action_total": review_actions,
            "acceptance_rate": (
                round(feedback.get("ACCEPTED", 0) / review_actions, 4)
                if review_actions
                else None
            ),
            "edit_rate": (
                round(feedback.get("EDITED", 0) / review_actions, 4)
                if review_actions
                else None
            ),
            "rejection_rate": (
                round(feedback.get("REJECTED", 0) / review_actions, 4)
                if review_actions
                else None
            ),
        },
        "breakdown": breakdown,
    }
