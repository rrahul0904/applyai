from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.interview_intelligence_models import InterviewIntelligenceQuestion, InterviewIntelligenceReport, InterviewQuestionEvidence
from app.interview_intelligence_service import evidence_confidence, freshness_score

router = APIRouter(prefix="/internal/interview-intelligence/evidence", tags=["internal-interview-intelligence"], dependencies=[Depends(require_internal_api)])


class EvidenceLinkWrite(BaseModel):
    question_id: uuid.UUID
    confidence: int = Field(default=80, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=4000)


def _recompute(session: Session, question: InterviewIntelligenceQuestion) -> None:
    rows = list(
        session.execute(
            select(InterviewIntelligenceReport)
            .join(InterviewQuestionEvidence, InterviewQuestionEvidence.report_id == InterviewIntelligenceReport.id)
            .where(
                InterviewQuestionEvidence.question_id == question.id,
                InterviewIntelligenceReport.moderation_status == "APPROVED",
            )
        ).scalars()
    )
    question.report_count = len(rows)
    if not rows:
        question.confidence = 0
        question.last_reported_at = None
        return
    latest = max((row.reported_at or row.created_at) for row in rows)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    age_days = max(0, int((datetime.now(timezone.utc) - latest).total_seconds() / 86400))
    source_diversity = len({row.source_type for row in rows})
    question.confidence = evidence_confidence(
        independent_reports=len(rows),
        source_diversity=source_diversity,
        age_days=age_days,
        moderation_approved=True,
    )
    question.last_reported_at = latest
    question.frequency_score = min(100, max(question.frequency_score, min(70, len(rows) * 8) + freshness_score(latest) // 3))
    labels = list(question.company_labels or [])
    for row in rows:
        if row.company_label and row.company_label.lower() not in {item.lower() for item in labels}:
            labels.append(row.company_label)
    question.company_labels = labels


@router.post("/reports/{report_id}/link")
def link_report(report_id: uuid.UUID, payload: EvidenceLinkWrite, session: Session = Depends(get_session)) -> dict[str, Any]:
    report = session.get(InterviewIntelligenceReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Interview report not found")
    if report.moderation_status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved reports may become evidence")
    question = session.get(InterviewIntelligenceQuestion, payload.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Interview question not found")
    existing = session.scalar(
        select(InterviewQuestionEvidence).where(
            InterviewQuestionEvidence.question_id == question.id,
            InterviewQuestionEvidence.report_id == report.id,
        )
    )
    if existing is None:
        existing = InterviewQuestionEvidence(
            question_id=question.id,
            report_id=report.id,
            confidence=payload.confidence,
            evidence_notes=payload.notes,
        )
        session.add(existing)
    else:
        existing.confidence = payload.confidence
        existing.evidence_notes = payload.notes
    _recompute(session, question)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Evidence link already exists") from exc
    return {
        "question_id": question.id,
        "report_id": report.id,
        "report_count": question.report_count,
        "confidence": question.confidence,
        "frequency_score": question.frequency_score,
        "last_reported_at": question.last_reported_at,
    }


@router.delete("/reports/{report_id}/questions/{question_id}")
def unlink_report(report_id: uuid.UUID, question_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    link = session.scalar(
        select(InterviewQuestionEvidence).where(
            InterviewQuestionEvidence.question_id == question_id,
            InterviewQuestionEvidence.report_id == report_id,
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Evidence link not found")
    question = session.get(InterviewIntelligenceQuestion, question_id)
    session.delete(link)
    session.flush()
    if question is not None:
        _recompute(session, question)
    session.commit()
    return {"unlinked": True, "question_id": question_id, "report_id": report_id}


@router.get("/questions/{question_id}")
def evidence_for_question(question_id: uuid.UUID, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = session.execute(
        select(InterviewQuestionEvidence, InterviewIntelligenceReport)
        .join(InterviewIntelligenceReport, InterviewIntelligenceReport.id == InterviewQuestionEvidence.report_id)
        .where(InterviewQuestionEvidence.question_id == question_id)
        .order_by(InterviewIntelligenceReport.reported_at.desc().nullslast(), InterviewIntelligenceReport.created_at.desc())
    )
    return [
        {
            "link_id": link.id,
            "report_id": report.id,
            "source_type": report.source_type,
            "company": report.company_label,
            "role": report.role,
            "reported_at": report.reported_at,
            "confidence": link.confidence,
            "notes": link.evidence_notes,
            "moderation_status": report.moderation_status,
        }
        for link, report in rows
    ]
