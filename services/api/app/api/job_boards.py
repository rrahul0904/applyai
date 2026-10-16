from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.job_board_models import (
    JobBoard,
    JobBoardClaim,
    JobBoardSource,
    JobDistributionPublication,
    JobOutboundClick,
    JobSeoAudit,
    JobSponsorshipCampaign,
    SearchConsoleSnapshot,
)
from app.job_source_models import JobSourceRegistry
from app.models import Company, Job, JobCompensation, JobLocation, JobSource, JobSourceLink, User


router = APIRouter(prefix="/job-boards", tags=["job-boards"])
internal_router = APIRouter(
    prefix="/internal/job-boards",
    tags=["internal-job-boards"],
    dependencies=[Depends(require_internal_api)],
)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CHANNELS = {"DIRECT", "REDDIT", "TELEGRAM", "NEWSLETTER", "LINKEDIN", "BLUESKY", "SEARCH", "PARTNER"}
DISTRIBUTION_CHANNELS = {"REDDIT", "TELEGRAM", "NEWSLETTER", "LINKEDIN", "BLUESKY"}


class BoardSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    website_url: str | None
    logo_url: str | None
    status: str
    visibility: str
    source_count: int
    active_job_count: int


class BoardJobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    location: str | None
    work_mode: str | None
    employment_type: str | None
    posted_at: datetime | None
    last_seen_at: datetime
    data_origin: str
    outbound_url: str


class BoardJobPage(BaseModel):
    items: list[BoardJobSummary]
    returned: int
    limit: int
    offset: int


class BoardCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=180)
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    website_url: str | None = None
    logo_url: str | None = None
    visibility: str = Field(default="PUBLIC", pattern="^(PUBLIC|PRIVATE|UNLISTED)$")
    metadata_json: dict = Field(default_factory=dict)


class BoardSourceCreate(BaseModel):
    source_registry_id: uuid.UUID
    priority: int = Field(default=50, ge=0, le=100)
    label: str | None = Field(default=None, max_length=160)


class BoardClaimCreate(BaseModel):
    proof_method: str = Field(default="DOMAIN", pattern="^(DOMAIN|EMAIL|DNS|MANUAL)$")
    evidence: dict = Field(default_factory=dict)


class BoardClaimReview(BaseModel):
    status: str = Field(pattern="^(APPROVED|REJECTED)$")
    review_notes: str | None = Field(default=None, max_length=4000)


class PublicationCreate(BaseModel):
    job_id: uuid.UUID
    board_id: uuid.UUID | None = None
    channel: str
    target: str = Field(min_length=1, max_length=255)
    payload: dict = Field(default_factory=dict)
    dry_run: bool = True
    idempotency_key: str = Field(min_length=8, max_length=160)


class PublicationTransition(BaseModel):
    approved_by_user_id: uuid.UUID | None = None


class PublicationReceipt(BaseModel):
    status: str = Field(pattern="^(PUBLISHED|FAILED|DRY_RUN)$")
    external_id: str | None = Field(default=None, max_length=255)
    external_url: str | None = None
    receipt_json: dict = Field(default_factory=dict)
    error_summary: str | None = Field(default=None, max_length=4000)


class SponsorshipCreate(BaseModel):
    board_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=180)
    sponsor_name: str = Field(min_length=1, max_length=180)
    destination_url: str | None = None
    budget_cents: int = Field(default=0, ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    metadata_json: dict = Field(default_factory=dict)


class SearchConsoleRow(BaseModel):
    board_id: uuid.UUID | None = None
    property_uri: str = Field(min_length=1, max_length=500)
    snapshot_date: date
    dimension_key: str = Field(default="page", max_length=48)
    dimension_value: str = Field(min_length=1)
    clicks: int = Field(default=0, ge=0)
    impressions: int = Field(default=0, ge=0)
    ctr: Decimal = Field(default=Decimal("0"), ge=0)
    position: Decimal = Field(default=Decimal("0"), ge=0)
    metadata_json: dict = Field(default_factory=dict)


class SeoAuditResponse(BaseModel):
    job_id: uuid.UUID
    board_id: uuid.UUID | None
    status: str
    score: int
    issues: list[str]
    schema_snapshot: dict


def _public_board(session: Session, slug: str) -> JobBoard:
    board = session.scalar(
        select(JobBoard).where(
            JobBoard.slug == slug,
            JobBoard.status == "ACTIVE",
            JobBoard.visibility == "PUBLIC",
        )
    )
    if board is None:
        raise HTTPException(status_code=404, detail="Job board not found")
    return board


def _source_ids(session: Session, board_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(JobBoardSource.source_registry_id).where(
                JobBoardSource.board_id == board_id,
                JobBoardSource.enabled.is_(True),
            )
        )
    )


def _board_job_statement(session: Session, board_id: uuid.UUID):
    source_ids = _source_ids(session, board_id)
    if not source_ids:
        return select(Job).where(Job.id.is_(None))
    registry_values = [str(value) for value in source_ids]
    return (
        select(Job)
        .join(JobSourceLink, JobSourceLink.job_id == Job.id)
        .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
        .where(
            JobSource.checkpoint["source_registry_id"].astext.in_(registry_values),
            Job.status == "ACTIVE",
        )
        .distinct()
    )


def _board_summary(session: Session, board: JobBoard) -> BoardSummary:
    source_count = session.scalar(
        select(func.count(JobBoardSource.id)).where(
            JobBoardSource.board_id == board.id,
            JobBoardSource.enabled.is_(True),
        )
    ) or 0
    active_job_count = session.scalar(
        select(func.count()).select_from(_board_job_statement(session, board.id).subquery())
    ) or 0
    return BoardSummary(
        id=board.id,
        slug=board.slug,
        name=board.name,
        description=board.description,
        website_url=board.website_url,
        logo_url=board.logo_url,
        status=board.status,
        visibility=board.visibility,
        source_count=int(source_count),
        active_job_count=int(active_job_count),
    )


def _job_source(session: Session, job_id: uuid.UUID) -> JobSource | None:
    return session.scalar(
        select(JobSource)
        .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
        .where(JobSourceLink.job_id == job_id)
        .order_by(JobSourceLink.is_primary.desc(), JobSource.id)
        .limit(1)
    )


def _source_registry_id(source: JobSource | None) -> uuid.UUID | None:
    if source is None or not source.checkpoint:
        return None
    value = source.checkpoint.get("source_registry_id")
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


def _safe_destination(source: JobSource | None) -> str:
    if source is None:
        raise HTTPException(status_code=404, detail="Application destination not found")
    destination = str((source.checkpoint or {}).get("canonical_apply_url") or source.source_url or "").strip()
    parsed = urlsplit(destination)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=409, detail="Application destination is not safe")
    return destination


def _jobposting_schema(session: Session, job: Job) -> dict:
    company = session.get(Company, job.company_id)
    location = session.scalar(select(JobLocation).where(JobLocation.job_id == job.id).limit(1))
    compensation = session.scalar(select(JobCompensation).where(JobCompensation.job_id == job.id).limit(1))
    source = _job_source(session, job.id)
    destination = _safe_destination(source)
    schema: dict = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.title,
        "description": job.description,
        "datePosted": job.posted_at.date().isoformat() if job.posted_at else job.first_seen_at.date().isoformat(),
        "hiringOrganization": {
            "@type": "Organization",
            "name": company.canonical_name if company else "Unknown employer",
        },
        "url": destination,
        "directApply": True,
    }
    if job.employment_type:
        schema["employmentType"] = job.employment_type
    if location:
        if location.work_mode == "REMOTE":
            schema["jobLocationType"] = "TELECOMMUTE"
        else:
            schema["jobLocation"] = {
                "@type": "Place",
                "address": {"@type": "PostalAddress", "addressLocality": location.location_text},
            }
    if compensation and (compensation.minimum is not None or compensation.maximum is not None):
        schema["baseSalary"] = {
            "@type": "MonetaryAmount",
            "currency": compensation.currency,
            "value": {
                "@type": "QuantitativeValue",
                "minValue": compensation.minimum,
                "maxValue": compensation.maximum,
                "unitText": compensation.interval,
            },
        }
    return schema


def _seo_audit(session: Session, job: Job, board_id: uuid.UUID | None) -> JobSeoAudit:
    schema = _jobposting_schema(session, job)
    issues: list[str] = []
    if len(job.title.strip()) < 3:
        issues.append("title_missing_or_too_short")
    if len(job.description.strip()) < 100:
        issues.append("description_too_short")
    if not schema.get("datePosted"):
        issues.append("date_posted_missing")
    if not schema.get("hiringOrganization", {}).get("name"):
        issues.append("hiring_organization_missing")
    if "jobLocation" not in schema and schema.get("jobLocationType") != "TELECOMMUTE":
        issues.append("job_location_missing")
    score = max(0, 100 - 15 * len(issues))
    audit = JobSeoAudit(
        job_id=job.id,
        board_id=board_id,
        status="PASS" if not issues else ("WARN" if score >= 70 else "FAIL"),
        score=score,
        issues=issues,
        schema_snapshot=schema,
    )
    session.add(audit)
    return audit


@router.get("", response_model=list[BoardSummary])
def list_boards(
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
):
    boards = list(
        session.scalars(
            select(JobBoard)
            .where(JobBoard.status == "ACTIVE", JobBoard.visibility == "PUBLIC")
            .order_by(JobBoard.name)
            .limit(limit)
        )
    )
    return [_board_summary(session, board) for board in boards]


@router.get("/{slug}", response_model=BoardSummary)
def get_board(slug: str, session: Session = Depends(get_session)):
    return _board_summary(session, _public_board(session, slug))


@router.get("/{slug}/jobs", response_model=BoardJobPage)
def list_board_jobs(
    slug: str,
    keyword: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    session: Session = Depends(get_session),
):
    board = _public_board(session, slug)
    statement = _board_job_statement(session, board.id)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        statement = statement.where(Job.title.ilike(pattern))
    if location:
        statement = statement.join(JobLocation, JobLocation.job_id == Job.id).where(
            JobLocation.location_text.ilike(f"%{location.strip()}%")
        )
    jobs = list(
        session.scalars(
            statement.order_by(Job.posted_at.desc().nullslast(), Job.first_seen_at.desc()).offset(offset).limit(limit)
        ).unique()
    )
    company_ids = {job.company_id for job in jobs}
    companies = {
        row.id: row
        for row in session.scalars(select(Company).where(Company.id.in_(company_ids)))
    } if company_ids else {}
    job_ids = [job.id for job in jobs]
    locations: dict[uuid.UUID, JobLocation] = {}
    if job_ids:
        for row in session.scalars(select(JobLocation).where(JobLocation.job_id.in_(job_ids)).order_by(JobLocation.id)):
            locations.setdefault(row.job_id, row)
    items: list[BoardJobSummary] = []
    for job in jobs:
        company = companies.get(job.company_id)
        location_row = locations.get(job.id)
        items.append(
            BoardJobSummary(
                id=job.id,
                title=job.title,
                company_name=company.canonical_name if company else "Unknown employer",
                location=location_row.location_text if location_row else None,
                work_mode=location_row.work_mode if location_row else None,
                employment_type=job.employment_type,
                posted_at=job.posted_at,
                last_seen_at=job.last_seen_at,
                data_origin=job.data_origin,
                outbound_url=f"/api/v1/job-boards/outbound/{job.id}?board={board.slug}",
            )
        )
    return BoardJobPage(items=items, returned=len(items), limit=limit, offset=offset)


@router.get("/{slug}/jobs/{job_id}/structured-data")
def structured_job_data(
    slug: str,
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    board = _public_board(session, slug)
    job = session.scalar(_board_job_statement(session, board.id).where(Job.id == job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found on this board")
    return _jobposting_schema(session, job)


@router.get("/outbound/{job_id}")
def outbound_job_click(
    job_id: uuid.UUID,
    request: Request,
    board: str | None = Query(default=None, max_length=180),
    channel: str = Query(default="DIRECT", max_length=48),
    session_id: str | None = Query(default=None, max_length=160),
    session: Session = Depends(get_session),
):
    channel = channel.upper()
    if channel not in CHANNELS:
        raise HTTPException(status_code=422, detail="Unsupported attribution channel")
    job = session.get(Job, job_id)
    if job is None or job.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Job not found")
    board_row = _public_board(session, board) if board else None
    if board_row is not None:
        board_job = session.scalar(_board_job_statement(session, board_row.id).where(Job.id == job_id))
        if board_job is None:
            raise HTTPException(status_code=404, detail="Job not found on this board")
    source = _job_source(session, job.id)
    destination = _safe_destination(source)
    referrer = request.headers.get("referer")
    referrer_host = urlsplit(referrer).hostname if referrer else None
    session_hash = hashlib.sha256(session_id.encode()).hexdigest() if session_id else None
    session.add(
        JobOutboundClick(
            job_id=job.id,
            board_id=board_row.id if board_row else None,
            source_registry_id=_source_registry_id(source),
            destination_url=destination,
            channel=channel,
            referrer_host=referrer_host,
            session_hash=session_hash,
            attribution={
                "utm_source": request.query_params.get("utm_source"),
                "utm_medium": request.query_params.get("utm_medium"),
                "utm_campaign": request.query_params.get("utm_campaign"),
            },
        )
    )
    session.commit()
    return RedirectResponse(destination, status_code=307)


@router.post("/{slug}/claim", status_code=201)
def submit_board_claim(
    slug: str,
    payload: BoardClaimCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    board = _public_board(session, slug)
    existing = session.scalar(
        select(JobBoardClaim).where(
            JobBoardClaim.board_id == board.id,
            JobBoardClaim.claimant_user_id == user.id,
            JobBoardClaim.status.in_(["PENDING", "APPROVED"]),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="An active claim already exists")
    claim = JobBoardClaim(
        board_id=board.id,
        claimant_user_id=user.id,
        proof_method=payload.proof_method,
        evidence=payload.evidence,
    )
    session.add(claim)
    session.commit()
    session.refresh(claim)
    return {"id": claim.id, "status": claim.status, "submitted_at": claim.submitted_at}


@internal_router.post("", status_code=201)
def create_board(payload: BoardCreate, session: Session = Depends(get_session)):
    slug = payload.slug.strip().lower()
    if not SLUG_RE.fullmatch(slug):
        raise HTTPException(status_code=422, detail="Board slug must be lowercase kebab-case")
    if session.scalar(select(JobBoard).where(JobBoard.slug == slug)) is not None:
        raise HTTPException(status_code=409, detail="Job board already exists")
    board = JobBoard(
        slug=slug,
        name=payload.name.strip(),
        description=payload.description,
        website_url=payload.website_url,
        logo_url=payload.logo_url,
        visibility=payload.visibility,
        metadata_json=payload.metadata_json,
    )
    session.add(board)
    session.commit()
    session.refresh(board)
    return _board_summary(session, board)


@internal_router.post("/{board_id}/sources", status_code=201)
def add_board_source(
    board_id: uuid.UUID,
    payload: BoardSourceCreate,
    session: Session = Depends(get_session),
):
    if session.get(JobBoard, board_id) is None:
        raise HTTPException(status_code=404, detail="Job board not found")
    if session.get(JobSourceRegistry, payload.source_registry_id) is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    existing = session.scalar(
        select(JobBoardSource).where(
            JobBoardSource.board_id == board_id,
            JobBoardSource.source_registry_id == payload.source_registry_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Source already belongs to board")
    membership = JobBoardSource(
        board_id=board_id,
        source_registry_id=payload.source_registry_id,
        priority=payload.priority,
        label=payload.label,
    )
    session.add(membership)
    session.commit()
    session.refresh(membership)
    return {"id": membership.id, "board_id": board_id, "source_registry_id": payload.source_registry_id}


@internal_router.post("/claims/{claim_id}/review")
def review_claim(
    claim_id: uuid.UUID,
    payload: BoardClaimReview,
    session: Session = Depends(get_session),
):
    claim = session.get(JobBoardClaim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Board claim not found")
    if claim.status != "PENDING":
        raise HTTPException(status_code=409, detail="Board claim is already reviewed")
    claim.status = payload.status
    claim.review_notes = payload.review_notes
    claim.reviewed_at = datetime.now(timezone.utc)
    if payload.status == "APPROVED":
        board = session.get(JobBoard, claim.board_id)
        if board is not None:
            board.owner_user_id = claim.claimant_user_id
    session.commit()
    return {"id": claim.id, "status": claim.status, "reviewed_at": claim.reviewed_at}


@internal_router.get("/{board_id}/analytics")
def board_analytics(board_id: uuid.UUID, session: Session = Depends(get_session)):
    board = session.get(JobBoard, board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Job board not found")
    active_jobs = session.scalar(
        select(func.count()).select_from(_board_job_statement(session, board.id).subquery())
    ) or 0
    clicks = session.scalar(
        select(func.count(JobOutboundClick.id)).where(JobOutboundClick.board_id == board.id)
    ) or 0
    publications = session.scalar(
        select(func.count(JobDistributionPublication.id)).where(JobDistributionPublication.board_id == board.id)
    ) or 0
    published = session.scalar(
        select(func.count(JobDistributionPublication.id)).where(
            JobDistributionPublication.board_id == board.id,
            JobDistributionPublication.status == "PUBLISHED",
        )
    ) or 0
    search_clicks = session.scalar(
        select(func.coalesce(func.sum(SearchConsoleSnapshot.clicks), 0)).where(SearchConsoleSnapshot.board_id == board.id)
    ) or 0
    search_impressions = session.scalar(
        select(func.coalesce(func.sum(SearchConsoleSnapshot.impressions), 0)).where(SearchConsoleSnapshot.board_id == board.id)
    ) or 0
    return {
        "board_id": board.id,
        "active_jobs": int(active_jobs),
        "outbound_clicks": int(clicks),
        "publication_receipts": int(publications),
        "published": int(published),
        "search_console_clicks": int(search_clicks),
        "search_console_impressions": int(search_impressions),
    }


@internal_router.post("/publications", status_code=201)
def create_publication(payload: PublicationCreate, session: Session = Depends(get_session)):
    channel = payload.channel.upper()
    if channel not in DISTRIBUTION_CHANNELS:
        raise HTTPException(status_code=422, detail="Unsupported distribution channel")
    if session.get(Job, payload.job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if payload.board_id and session.get(JobBoard, payload.board_id) is None:
        raise HTTPException(status_code=404, detail="Job board not found")
    existing = session.scalar(
        select(JobDistributionPublication).where(
            JobDistributionPublication.idempotency_key == payload.idempotency_key
        )
    )
    if existing is not None:
        return {
            "id": existing.id,
            "status": existing.status,
            "dry_run": existing.dry_run,
            "idempotent_replay": True,
        }
    canonical_payload = json.dumps(payload.payload, sort_keys=True, separators=(",", ":"))
    publication = JobDistributionPublication(
        job_id=payload.job_id,
        board_id=payload.board_id,
        channel=channel,
        target=payload.target,
        status="DRAFT",
        idempotency_key=payload.idempotency_key,
        payload_hash=hashlib.sha256(canonical_payload.encode()).hexdigest(),
        dry_run=payload.dry_run,
        receipt_json={"prepared_payload": payload.payload},
    )
    session.add(publication)
    session.commit()
    session.refresh(publication)
    return {"id": publication.id, "status": publication.status, "dry_run": publication.dry_run, "idempotent_replay": False}


@internal_router.post("/publications/{publication_id}/approve")
def approve_publication(
    publication_id: uuid.UUID,
    payload: PublicationTransition,
    session: Session = Depends(get_session),
):
    publication = session.get(JobDistributionPublication, publication_id)
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    if publication.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Publication is not awaiting approval")
    publication.status = "APPROVED"
    publication.approved_by_user_id = payload.approved_by_user_id
    publication.approved_at = datetime.now(timezone.utc)
    session.commit()
    return {"id": publication.id, "status": publication.status, "approved_at": publication.approved_at}


@internal_router.post("/publications/{publication_id}/receipt")
def record_publication_receipt(
    publication_id: uuid.UUID,
    payload: PublicationReceipt,
    session: Session = Depends(get_session),
):
    publication = session.get(JobDistributionPublication, publication_id)
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    if publication.status not in {"APPROVED", "DRAFT"}:
        raise HTTPException(status_code=409, detail="Publication already has a terminal receipt")
    if payload.status == "PUBLISHED" and publication.dry_run:
        raise HTTPException(status_code=409, detail="Dry-run publication cannot be marked as externally published")
    publication.status = payload.status
    publication.external_id = payload.external_id
    publication.external_url = payload.external_url
    publication.receipt_json = {**(publication.receipt_json or {}), **payload.receipt_json}
    publication.error_summary = payload.error_summary
    publication.published_at = datetime.now(timezone.utc) if payload.status in {"PUBLISHED", "DRY_RUN"} else None
    session.commit()
    return {"id": publication.id, "status": publication.status, "published_at": publication.published_at}


@internal_router.post("/sponsorships", status_code=201)
def create_sponsorship(payload: SponsorshipCreate, session: Session = Depends(get_session)):
    if payload.board_id and session.get(JobBoard, payload.board_id) is None:
        raise HTTPException(status_code=404, detail="Job board not found")
    if payload.starts_at and payload.ends_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Sponsorship end must be after start")
    campaign = JobSponsorshipCampaign(**payload.model_dump())
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return {"id": campaign.id, "status": campaign.status, "budget_cents": campaign.budget_cents}


@internal_router.post("/search-console/snapshots", status_code=201)
def ingest_search_console_snapshot(payload: SearchConsoleRow, session: Session = Depends(get_session)):
    if payload.board_id and session.get(JobBoard, payload.board_id) is None:
        raise HTTPException(status_code=404, detail="Job board not found")
    existing = session.scalar(
        select(SearchConsoleSnapshot).where(
            SearchConsoleSnapshot.property_uri == payload.property_uri,
            SearchConsoleSnapshot.snapshot_date == payload.snapshot_date,
            SearchConsoleSnapshot.dimension_key == payload.dimension_key,
            SearchConsoleSnapshot.dimension_value == payload.dimension_value,
        )
    )
    if existing is None:
        existing = SearchConsoleSnapshot(**payload.model_dump())
        session.add(existing)
    else:
        for key, value in payload.model_dump().items():
            setattr(existing, key, value)
    session.commit()
    session.refresh(existing)
    return {"id": existing.id, "snapshot_date": existing.snapshot_date, "clicks": existing.clicks, "impressions": existing.impressions}


@internal_router.post("/{board_id}/jobs/{job_id}/seo-audit", response_model=SeoAuditResponse)
def audit_job_seo(
    board_id: uuid.UUID,
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    board = session.get(JobBoard, board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Job board not found")
    job = session.scalar(_board_job_statement(session, board.id).where(Job.id == job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found on this board")
    audit = _seo_audit(session, job, board.id)
    session.commit()
    return SeoAuditResponse(
        job_id=job.id,
        board_id=board.id,
        status=audit.status,
        score=audit.score,
        issues=list(audit.issues),
        schema_snapshot=audit.schema_snapshot,
    )
