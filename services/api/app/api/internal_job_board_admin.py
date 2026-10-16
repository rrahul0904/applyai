from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.job_board_models import (
    JobBoard,
    JobBoardClaim,
    JobBoardSource,
    JobDistributionPublication,
    JobOutboundClick,
    JobSponsorshipCampaign,
    SearchConsoleSnapshot,
)


router = APIRouter(
    prefix="/internal/job-board-network",
    tags=["internal-job-board-network"],
    dependencies=[Depends(require_internal_api)],
)


class BoardAdminRow(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    status: str
    visibility: str
    owner_user_id: uuid.UUID | None
    source_count: int
    outbound_clicks: int
    created_at: datetime


@router.get("/summary")
def summary(session: Session = Depends(get_session)):
    def count(model, *criteria) -> int:
        return int(session.scalar(select(func.count()).select_from(model).where(*criteria)) or 0)

    search_clicks = int(session.scalar(select(func.coalesce(func.sum(SearchConsoleSnapshot.clicks), 0))) or 0)
    search_impressions = int(session.scalar(select(func.coalesce(func.sum(SearchConsoleSnapshot.impressions), 0))) or 0)
    return {
        "boards": count(JobBoard),
        "public_boards": count(JobBoard, JobBoard.status == "ACTIVE", JobBoard.visibility == "PUBLIC"),
        "pending_claims": count(JobBoardClaim, JobBoardClaim.status == "PENDING"),
        "outbound_clicks": count(JobOutboundClick),
        "publication_receipts": count(JobDistributionPublication),
        "published": count(JobDistributionPublication, JobDistributionPublication.status == "PUBLISHED"),
        "dry_runs": count(JobDistributionPublication, JobDistributionPublication.status == "DRY_RUN"),
        "failed_publications": count(JobDistributionPublication, JobDistributionPublication.status == "FAILED"),
        "sponsorship_campaigns": count(JobSponsorshipCampaign),
        "active_sponsorships": count(JobSponsorshipCampaign, JobSponsorshipCampaign.status == "ACTIVE"),
        "search_console_clicks": search_clicks,
        "search_console_impressions": search_impressions,
    }


@router.get("/boards", response_model=list[BoardAdminRow])
def boards(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    rows = list(session.scalars(select(JobBoard).order_by(JobBoard.created_at.desc()).limit(limit)))
    result: list[BoardAdminRow] = []
    for board in rows:
        sources = int(session.scalar(select(func.count(JobBoardSource.id)).where(JobBoardSource.board_id == board.id)) or 0)
        clicks = int(session.scalar(select(func.count(JobOutboundClick.id)).where(JobOutboundClick.board_id == board.id)) or 0)
        result.append(
            BoardAdminRow(
                id=board.id,
                slug=board.slug,
                name=board.name,
                status=board.status,
                visibility=board.visibility,
                owner_user_id=board.owner_user_id,
                source_count=sources,
                outbound_clicks=clicks,
                created_at=board.created_at,
            )
        )
    return result


@router.get("/claims")
def claims(
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    statement = select(JobBoardClaim).order_by(JobBoardClaim.submitted_at.desc())
    if status:
        statement = statement.where(JobBoardClaim.status == status.upper())
    rows = list(session.scalars(statement.limit(limit)))
    return [
        {
            "id": row.id,
            "board_id": row.board_id,
            "claimant_user_id": row.claimant_user_id,
            "status": row.status,
            "proof_method": row.proof_method,
            "evidence": row.evidence,
            "submitted_at": row.submitted_at,
            "reviewed_at": row.reviewed_at,
        }
        for row in rows
    ]


@router.get("/publications")
def publications(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    rows = list(
        session.scalars(
            select(JobDistributionPublication)
            .order_by(JobDistributionPublication.created_at.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": row.id,
            "job_id": row.job_id,
            "board_id": row.board_id,
            "channel": row.channel,
            "target": row.target,
            "status": row.status,
            "dry_run": row.dry_run,
            "external_url": row.external_url,
            "error_summary": row.error_summary,
            "created_at": row.created_at,
            "published_at": row.published_at,
        }
        for row in rows
    ]


@router.get("/sponsorships")
def sponsorships(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    rows = list(
        session.scalars(
            select(JobSponsorshipCampaign)
            .order_by(JobSponsorshipCampaign.created_at.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": row.id,
            "board_id": row.board_id,
            "name": row.name,
            "sponsor_name": row.sponsor_name,
            "status": row.status,
            "budget_cents": row.budget_cents,
            "spent_cents": row.spent_cents,
            "starts_at": row.starts_at,
            "ends_at": row.ends_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]
