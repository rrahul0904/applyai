from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.ai.quality import ai_quality_metrics
from app.core.database import get_session
from app.core.internal_auth import require_internal_api


router = APIRouter(
    prefix="/internal/ai-quality",
    tags=["internal-ai-quality"],
    dependencies=[Depends(require_internal_api)],
)


@router.get("/metrics")
def get_ai_quality_metrics(
    window_hours: int = Query(default=24, ge=1, le=24 * 90),
    session: Session = Depends(get_session),
):
    return ai_quality_metrics(session, window_hours=window_hours)
