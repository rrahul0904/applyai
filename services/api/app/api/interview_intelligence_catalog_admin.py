from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.interview_intelligence_models import InterviewIntelligenceQuestion

router = APIRouter(
    prefix="/internal/interview-intelligence/catalog",
    tags=["internal-interview-intelligence"],
    dependencies=[Depends(require_internal_api)],
)


@router.get("/questions")
def list_questions(
    limit: int = Query(default=250, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    items = list(
        session.scalars(
            select(InterviewIntelligenceQuestion)
            .order_by(
                InterviewIntelligenceQuestion.published.desc(),
                InterviewIntelligenceQuestion.frequency_score.desc(),
                InterviewIntelligenceQuestion.title,
            )
            .limit(limit)
        )
    )
    return [
        {
            "id": item.id,
            "slug": item.slug,
            "title": item.title,
            "track": item.track,
            "difficulty": item.difficulty,
            "companies": item.company_labels or [],
            "confidence": item.confidence,
            "report_count": item.report_count,
            "published": item.published,
        }
        for item in items
    ]
