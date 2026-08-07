from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.context import build_career_ai_context, get_owned_active_job
from app.ai.prompts import PROMPT_VERSION, SCHEMA_VERSION
from app.ai.runtime import execute_ai_run
from app.api.candidate_workspace import get_or_create_application
from app.career_models import (
    AIArtifact,
    AIJobRun,
    ApplicationQuestionDraft,
    CandidateAIArtifactFeedback,
    CoverLetter,
    ResumeTailoring,
    ResumeTailoringRevision,
)
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.models import User


router = APIRouter(prefix="/career-v2", tags=["career intelligence v2"])

TASK_PATHS = {
    "deep-match": "AI_DEEP_MATCH",
    "resume-tailoring": "AI_RESUME_TAILOR",
    "application-copilot": "AI_APPLICATION_COPILOT",
    "interview-prep": "AI_INTERVIEW_PREP",
}
APPLICATION_TASKS = {"AI_RESUME_TAILOR", "AI_APPLICATION_COPILOT"}


class RevisionReviewWrite(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    text: str | None = Field(default=None, max_length=5000)


class CoverLetterReviewWrite(BaseModel):
    body: str = Field(min_length=1, max_length=12000)
    candidate_verified: bool = True


class QuestionReviewWrite(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)
    candidate_verified: bool = True


class FeedbackWrite(BaseModel):
    action: Literal["ACCEPTED", "EDITED", "REJECTED", "HELPFUL", "NOT_HELPFUL"]
    metadata: dict = Field(default_factory=dict)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _run_payload(run: AIJobRun) -> dict:
    return {
        "id": run.id,
        "task_type": run.task_type,
        "job_id": run.job_id,
        "application_id": run.application_id,
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "prompt_version": run.prompt_version,
        "schema_version": run.schema_version,
        "input_hash": run.input_hash,
        "output": run.output_json,
        "evidence_refs": run.evidence_refs,
        "attempt_count": run.attempt_count,
        "latency_ms": run.latency_ms,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "estimated_cost_usd": (
            float(run.estimated_cost_usd)
            if run.estimated_cost_usd is not None
            else None
        ),
        "error_code": run.error_code,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }


def _input_hash(context: dict) -> str:
    encoded = json.dumps(
        context,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _queue_run(
    *,
    task_type: str,
    job_id: uuid.UUID,
    user: User,
    session: Session,
    settings: Settings,
) -> AIJobRun:
    job = get_owned_active_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    context = build_career_ai_context(session, user, job)
    digest = _input_hash(context)
    idempotency_key = f"{user.id}:{job.id}:{task_type}:{PROMPT_VERSION}:{digest}"
    existing = session.scalar(
        select(AIJobRun).where(AIJobRun.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing

    application = None
    if task_type in APPLICATION_TASKS:
        application = get_or_create_application(job=job, user=user, session=session)

    run = AIJobRun(
        user_id=user.id,
        job_id=job.id,
        application_id=application.id if application else None,
        task_type=task_type,
        provider=settings.ai_provider,
        model=(
            settings.openai_model
            if settings.ai_provider == "openai"
            else "deterministic-evidence-v1"
        ),
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        input_hash=digest,
        idempotency_key=idempotency_key,
        status="QUEUED",
        input_json=context,
    )
    session.add(run)
    session.flush()
    add_task_outbox_event(
        session,
        task=Task(
            task_type=task_type,
            payload={"run_id": str(run.id)},
            idempotency_key=f"ai-run:{run.id}:1",
        ),
        aggregate_type="AIJobRun",
        aggregate_id=run.id,
    )
    session.commit()

    if settings.task_queue_provider == "memory":
        execute_ai_run(run.id, settings)
        session.expire_all()
        return session.get(AIJobRun, run.id) or run
    return run


@router.post("/jobs/{job_id}/{task_path}")
def create_ai_task(
    job_id: uuid.UUID,
    task_path: Literal[
        "deep-match",
        "resume-tailoring",
        "application-copilot",
        "interview-prep",
    ],
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    run = _queue_run(
        task_type=TASK_PATHS[task_path],
        job_id=job_id,
        user=user,
        session=session,
        settings=settings,
    )
    return _run_payload(run)


@router.get("/runs/{run_id}")
def get_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    run = session.scalar(
        select(AIJobRun).where(
            AIJobRun.id == run_id,
            AIJobRun.user_id == user.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="AI run not found")
    return _run_payload(run)


@router.post("/runs/{run_id}/retry")
def retry_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    run = session.scalar(
        select(AIJobRun).where(
            AIJobRun.id == run_id,
            AIJobRun.user_id == user.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="AI run not found")
    if run.status != "FAILED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed AI runs can be retried",
        )

    run.status = "QUEUED"
    run.error_code = None
    run.error_summary = None
    add_task_outbox_event(
        session,
        task=Task(
            task_type=run.task_type,
            payload={"run_id": str(run.id)},
            idempotency_key=f"ai-run:{run.id}:{run.attempt_count + 1}",
        ),
        aggregate_type="AIJobRun",
        aggregate_id=run.id,
    )
    session.commit()

    if settings.task_queue_provider == "memory":
        execute_ai_run(run.id, settings)
        session.expire_all()
        run = session.get(AIJobRun, run.id) or run
    return _run_payload(run)


@router.get("/artifacts")
def list_artifacts(
    job_id: uuid.UUID | None = Query(default=None),
    artifact_type: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    query = select(AIArtifact).where(AIArtifact.user_id == user.id)
    if job_id is not None:
        query = query.where(AIArtifact.job_id == job_id)
    if artifact_type:
        query = query.where(AIArtifact.artifact_type == artifact_type)
    rows = list(
        session.scalars(query.order_by(AIArtifact.created_at.desc()).limit(limit))
    )
    return {
        "items": [
            {
                "id": row.id,
                "run_id": row.run_id,
                "job_id": row.job_id,
                "application_id": row.application_id,
                "artifact_type": row.artifact_type,
                "status": row.status,
                "version": row.version,
                "content": row.content_json,
                "evidence": row.evidence_json,
                "candidate_verified": row.candidate_verified,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.patch("/tailorings/{tailoring_id}/revisions/{position}")
def review_resume_revision(
    tailoring_id: uuid.UUID,
    position: int,
    payload: RevisionReviewWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    tailoring = session.scalar(
        select(ResumeTailoring).where(
            ResumeTailoring.id == tailoring_id,
            ResumeTailoring.user_id == user.id,
        )
    )
    if tailoring is None:
        raise HTTPException(status_code=404, detail="Resume tailoring not found")

    revision = session.scalar(
        select(ResumeTailoringRevision).where(
            ResumeTailoringRevision.tailoring_id == tailoring.id,
            ResumeTailoringRevision.position == position,
        )
    )
    if revision is None:
        raise HTTPException(
            status_code=404,
            detail="Resume tailoring revision not found",
        )

    revision.candidate_decision = payload.decision
    revision.candidate_text = payload.text or revision.suggested_text
    revision.reviewed_at = utcnow()
    session.flush()

    decisions = list(
        session.scalars(
            select(ResumeTailoringRevision.candidate_decision).where(
                ResumeTailoringRevision.tailoring_id == tailoring.id
            )
        )
    )
    if decisions and all(item in {"APPROVED", "REJECTED"} for item in decisions):
        tailoring.status = "REVIEWED"
    else:
        tailoring.status = "NEEDS_REVIEW"
    session.commit()

    return {
        "tailoring_id": tailoring.id,
        "position": revision.position,
        "decision": revision.candidate_decision,
        "text": revision.candidate_text,
        "status": tailoring.status,
    }


@router.patch("/cover-letters/{cover_letter_id}")
def review_cover_letter(
    cover_letter_id: uuid.UUID,
    payload: CoverLetterReviewWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.scalar(
        select(CoverLetter).where(
            CoverLetter.id == cover_letter_id,
            CoverLetter.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Cover letter not found")

    row.body = payload.body
    row.candidate_verified = payload.candidate_verified
    artifact = session.get(AIArtifact, row.artifact_id)
    if artifact and artifact.user_id == user.id:
        artifact.candidate_verified = payload.candidate_verified
    session.commit()
    return {
        "id": row.id,
        "body": row.body,
        "candidate_verified": row.candidate_verified,
    }


@router.patch("/question-drafts/{draft_id}")
def review_question_draft(
    draft_id: uuid.UUID,
    payload: QuestionReviewWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.scalar(
        select(ApplicationQuestionDraft)
        .join(AIArtifact, AIArtifact.id == ApplicationQuestionDraft.artifact_id)
        .where(
            ApplicationQuestionDraft.id == draft_id,
            AIArtifact.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Application answer draft not found",
        )

    row.candidate_text = payload.answer
    row.candidate_verified = payload.candidate_verified
    row.reviewed_at = utcnow()
    session.commit()
    return {
        "id": row.id,
        "question": row.question,
        "answer": row.candidate_text,
        "candidate_verified": row.candidate_verified,
    }


@router.post("/artifacts/{artifact_id}/feedback")
def record_artifact_feedback(
    artifact_id: uuid.UUID,
    payload: FeedbackWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    artifact = session.scalar(
        select(AIArtifact).where(
            AIArtifact.id == artifact_id,
            AIArtifact.user_id == user.id,
        )
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="AI artifact not found")

    feedback = CandidateAIArtifactFeedback(
        artifact_id=artifact.id,
        user_id=user.id,
        action=payload.action,
        metadata_json=payload.metadata,
    )
    session.add(feedback)
    session.commit()
    return {
        "id": feedback.id,
        "artifact_id": artifact.id,
        "action": feedback.action,
    }
