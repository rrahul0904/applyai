from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.operator_auth import require_operator_or_internal
from app.interview_intelligence_models import InterviewIntelligenceQuestion, InterviewQuestionEvidence

router = APIRouter(
    prefix="/internal/interview-intelligence-catalog",
    tags=["internal interview intelligence catalog"],
    dependencies=[Depends(require_operator_or_internal)],
)


@router.get("/questions")
def list_questions(
    published: bool | None = None,
    limit: int = Query(default=250, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict]:
    statement = select(InterviewIntelligenceQuestion)
    if published is not None:
        statement = statement.where(InterviewIntelligenceQuestion.published.is_(published))
    rows = list(
        session.scalars(
            statement.order_by(
                InterviewIntelligenceQuestion.track,
                InterviewIntelligenceQuestion.frequency_score.desc(),
                InterviewIntelligenceQuestion.title,
            ).limit(limit)
        )
    )
    return [
        {
            "id": str(row.id),
            "slug": row.slug,
            "title": row.title,
            "track": row.track,
            "difficulty": row.difficulty,
            "published": row.published,
            "frequency_score": row.frequency_score,
            "confidence": row.confidence,
            "report_count": row.report_count,
            "companies": row.company_labels or [],
            "stages": row.stages or [],
        }
        for row in rows
    ]


@router.get("/evidence")
def list_evidence(
    limit: int = Query(default=250, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict]:
    rows = list(session.scalars(select(InterviewQuestionEvidence).order_by(InterviewQuestionEvidence.created_at.desc()).limit(limit)))
    return [
        {
            "id": str(row.id),
            "question_id": str(row.question_id),
            "report_id": str(row.report_id),
            "confidence": row.confidence,
            "evidence_notes": row.evidence_notes,
            "created_at": row.created_at,
        }
        for row in rows
    ]
