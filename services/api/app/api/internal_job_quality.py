from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.jobs.quality import quality_metrics, source_coverage_metrics


router = APIRouter(
    prefix="/internal/job-quality",
    tags=["internal-job-quality"],
    dependencies=[Depends(require_internal_api)],
)


@router.get("/metrics")
def get_quality_metrics(
    window_hours: int = Query(default=24, ge=1, le=24 * 90),
    session: Session = Depends(get_session),
):
    return quality_metrics(session, window_hours=window_hours)


@router.get("/source-coverage")
def get_source_coverage(session: Session = Depends(get_session)):
    return source_coverage_metrics(session)
