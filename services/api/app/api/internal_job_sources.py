from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.durability_models import JobIngestionRun
from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import ConnectorHealth, GreenhouseJobBoardConnector
from app.jobs.contracts import JobSourceType, SourceHealthStatus, SourceTrustLevel
from app.jobs.registry import run_registered_source
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline


router = APIRouter(
    prefix="/internal/job-sources",
    tags=["internal-job-sources"],
    dependencies=[Depends(require_internal_api)],
)


class JobSourceCreate(BaseModel):
    source_type: JobSourceType
    source_name: str = Field(min_length=1, max_length=160)
    source_identity: str = Field(min_length=1, max_length=255)
    base_url: str | None = None
    careers_url: str | None = None
    configuration: dict = Field(default_factory=dict)
    trust_level: SourceTrustLevel = SourceTrustLevel.OFFICIAL_ATS
    enabled: bool = True
    crawl_allowed: bool = True
    crawl_interval_seconds: int = Field(default=21_600, ge=300, le=2_592_000)


class JobSourcePatch(BaseModel):
    source_name: str | None = Field(default=None, min_length=1, max_length=160)
    base_url: str | None = None
    careers_url: str | None = None
    configuration: dict | None = None
    trust_level: SourceTrustLevel | None = None
    enabled: bool | None = None
    crawl_allowed: bool | None = None
    crawl_interval_seconds: int | None = Field(default=None, ge=300, le=2_592_000)


class JobSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID | None
    source_type: str
    source_name: str
    source_identity: str
    base_url: str | None
    careers_url: str | None
    configuration: dict
    trust_level: str
    enabled: bool
    crawl_allowed: bool
    health_status: str
    consecutive_failures: int
    last_job_count: int
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_error_category: str | None
    last_error_summary: str | None
    crawl_interval_seconds: int
    next_run_at: datetime
    locked_at: datetime | None
    locked_by: str | None
    lease_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobSourceRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID | None
    source_type: str | None
    connector: str
    source_company: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    status: str
    fetched: int
    valid: int
    invalid: int
    created: int
    updated: int
    unchanged: int
    deduplicated: int
    failed: int
    stale: int
    closed: int
    error_category: str | None
    error_summary: str | None


class ManualRunResponse(BaseModel):
    source_id: uuid.UUID
    counts: dict[str, int]


class OfficialGreenhouseImport(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    postings: list[dict] = Field(min_length=1, max_length=50)


class _ImportedGreenhousePayloadConnector(GreenhouseJobBoardConnector):
    """Ingest a bounded, operator-supplied Greenhouse response without outbound API egress."""

    def __init__(
        self,
        *,
        board_token: str,
        company_name: str,
        postings: list[dict],
    ) -> None:
        super().__init__(board_token)
        self.company_name = company_name
        self.postings = postings

    def fetch(self, checkpoint: dict | None) -> list[dict]:
        del checkpoint
        fetched_at = datetime.now(timezone.utc)
        records: list[dict] = []
        for item in self.postings:
            if not isinstance(item, dict) or item.get("id") is None or not item.get("title"):
                continue
            post_id = str(item["id"])
            internal_job_id = item.get("internal_job_id")
            records.append(
                {
                    **item,
                    "_applyai_company_name": self.company_name,
                    "_applyai_board_token": self.board_token,
                    "_applyai_greenhouse_post_id": post_id,
                    "_applyai_internal_job_id": (
                        str(internal_job_id) if internal_job_id is not None else None
                    ),
                    "_applyai_source_updated_at": item.get("updated_at"),
                    "_applyai_fetched_at": fetched_at.isoformat(),
                    "_applyai_company_source_url": (
                        f"{self.base_url}/{self.board_token}"
                    ),
                    "data_origin": "GREENHOUSE_PUBLIC_API",
                }
            )
        self._last_fetch_at = fetched_at
        self._last_count = len(records)
        self._company_name = self.company_name
        return records

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            healthy=True,
            checked_at=datetime.now(timezone.utc),
            detail="Operator-supplied official Greenhouse payload",
        )


def _get_source(session: Session, source_id: uuid.UUID) -> JobSourceRegistry:
    source = session.get(JobSourceRegistry, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    return source


@router.get("", response_model=list[JobSourceResponse])
def list_job_sources(
    health_status: SourceHealthStatus | None = None,
    source_type: JobSourceType | None = None,
    enabled: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    query = select(JobSourceRegistry).order_by(
        JobSourceRegistry.source_type,
        JobSourceRegistry.source_name,
    )
    if health_status is not None:
        query = query.where(JobSourceRegistry.health_status == health_status.value)
    if source_type is not None:
        query = query.where(JobSourceRegistry.source_type == source_type.value)
    if enabled is not None:
        query = query.where(JobSourceRegistry.enabled.is_(enabled))
    return list(session.scalars(query.limit(limit)))


@router.post("", response_model=JobSourceResponse, status_code=201)
def create_job_source(
    payload: JobSourceCreate,
    session: Session = Depends(get_session),
):
    existing = session.scalar(
        select(JobSourceRegistry).where(
            JobSourceRegistry.source_type == payload.source_type.value,
            JobSourceRegistry.source_identity == payload.source_identity,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Job source already exists")
    source = JobSourceRegistry(
        source_type=payload.source_type.value,
        source_name=payload.source_name,
        source_identity=payload.source_identity,
        base_url=payload.base_url,
        careers_url=payload.careers_url,
        configuration=payload.configuration,
        trust_level=payload.trust_level.value,
        enabled=payload.enabled,
        crawl_allowed=payload.crawl_allowed,
        health_status=(
            SourceHealthStatus.HEALTHY.value
            if payload.enabled
            else SourceHealthStatus.DISABLED.value
        ),
        crawl_interval_seconds=payload.crawl_interval_seconds,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@router.get("/{source_id}", response_model=JobSourceResponse)
def get_job_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    return _get_source(session, source_id)


@router.patch("/{source_id}", response_model=JobSourceResponse)
def patch_job_source(
    source_id: uuid.UUID,
    payload: JobSourcePatch,
    session: Session = Depends(get_session),
):
    source = _get_source(session, source_id)
    changes = payload.model_dump(exclude_unset=True)
    trust_level = changes.pop("trust_level", None)
    if trust_level is not None:
        source.trust_level = trust_level.value
    for key, value in changes.items():
        setattr(source, key, value)
    if source.enabled and source.health_status == SourceHealthStatus.DISABLED.value:
        source.health_status = SourceHealthStatus.HEALTHY.value
    if not source.enabled:
        source.health_status = SourceHealthStatus.DISABLED.value
    session.commit()
    session.refresh(source)
    return source


@router.post("/{source_id}/run", response_model=ManualRunResponse)
def run_job_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    source = _get_source(session, source_id)
    if not source.enabled or not source.crawl_allowed:
        raise HTTPException(status_code=409, detail="Job source is disabled or blocked")
    session.commit()
    counts = run_registered_source(source_id)
    return ManualRunResponse(source_id=source_id, counts=counts)


@router.post("/{source_id}/import-greenhouse", response_model=ManualRunResponse)
def import_official_greenhouse_payload(
    source_id: uuid.UUID,
    payload: OfficialGreenhouseImport,
    session: Session = Depends(get_session),
):
    source = _get_source(session, source_id)
    if source.source_type != JobSourceType.GREENHOUSE.value:
        raise HTTPException(status_code=409, detail="Source is not a Greenhouse board")
    if not source.enabled or not source.crawl_allowed:
        raise HTTPException(status_code=409, detail="Job source is disabled or blocked")
    board_token = str(
        (source.configuration or {}).get("board_token") or source.source_identity
    ).strip()
    connector = _ImportedGreenhousePayloadConnector(
        board_token=board_token,
        company_name=payload.company_name,
        postings=payload.postings,
    )
    counts = RegisteredSourceIngestionPipeline(session).run(source, connector)
    connector.close()
    return ManualRunResponse(source_id=source_id, counts=counts)


@router.post("/{source_id}/disable", response_model=JobSourceResponse)
def disable_job_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    source = _get_source(session, source_id)
    source.enabled = False
    source.health_status = SourceHealthStatus.DISABLED.value
    source.locked_at = None
    source.locked_by = None
    source.lease_expires_at = None
    session.commit()
    session.refresh(source)
    return source


@router.post("/{source_id}/enable", response_model=JobSourceResponse)
def enable_job_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    source = _get_source(session, source_id)
    source.enabled = True
    source.health_status = SourceHealthStatus.HEALTHY.value
    source.consecutive_failures = 0
    session.commit()
    session.refresh(source)
    return source


@router.get("/{source_id}/runs", response_model=list[JobSourceRunResponse])
def list_job_source_runs(
    source_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    _get_source(session, source_id)
    return list(
        session.scalars(
            select(JobIngestionRun)
            .where(JobIngestionRun.source_id == source_id)
            .order_by(JobIngestionRun.started_at.desc(), JobIngestionRun.id.desc())
            .limit(limit)
        )
    )
