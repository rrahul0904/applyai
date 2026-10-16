from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.job_board_models import JobBoard, JobDistributionPublication
from app.jobs.distribution import DistributionError, DistributionMessage, DistributionPublisher
from app.models import Company, Job, JobSource, JobSourceLink


router = APIRouter(
    prefix="/internal/job-boards/publications",
    tags=["internal-job-board-distribution"],
    dependencies=[Depends(require_internal_api)],
)


def _job_source(session: Session, job_id: uuid.UUID) -> JobSource | None:
    return session.scalar(
        select(JobSource)
        .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
        .where(JobSourceLink.job_id == job_id)
        .order_by(JobSourceLink.is_primary.desc(), JobSource.id)
        .limit(1)
    )


@router.post("/{publication_id}/publish")
def publish_distribution(
    publication_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    publication = session.get(JobDistributionPublication, publication_id)
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    if publication.status not in {"APPROVED", "DRAFT"}:
        raise HTTPException(status_code=409, detail="Publication already has a terminal receipt")
    if not publication.dry_run and publication.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Live publication requires explicit approval")

    job = session.get(Job, publication.job_id)
    if job is None or job.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active jobs can be distributed")
    company = session.get(Company, job.company_id)
    source = _job_source(session, job.id)
    destination = str((source.checkpoint or {}).get("canonical_apply_url") if source else "") or (source.source_url if source else "")
    if not destination.startswith(("https://", "http://")):
        raise HTTPException(status_code=409, detail="Job does not have a safe public destination")

    prepared = dict(publication.receipt_json or {}).get("prepared_payload") or {}
    board = session.get(JobBoard, publication.board_id) if publication.board_id else None
    message = DistributionMessage(
        title=str(prepared.get("title") or f"{job.title} at {company.canonical_name if company else 'an employer'}"),
        text=str(prepared.get("text") or prepared.get("description") or job.description[:800]),
        url=str(prepared.get("url") or destination),
        target=publication.target,
        metadata={
            "job_id": str(job.id),
            "board_id": str(board.id) if board else None,
            "board_slug": board.slug if board else None,
            "idempotency_key": publication.idempotency_key,
        },
    )

    publisher = DistributionPublisher()
    try:
        receipt = publisher.publish(publication.channel, message, dry_run=publication.dry_run)
    except DistributionError as exc:
        publication.status = "FAILED"
        publication.error_summary = str(exc)[:4000]
        session.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        publication.status = "FAILED"
        publication.error_summary = f"{type(exc).__name__}: external provider request failed"[:4000]
        session.commit()
        raise HTTPException(status_code=502, detail="External distribution provider rejected the publication") from exc
    finally:
        publisher.close()

    publication.status = receipt.status
    publication.external_id = receipt.external_id
    publication.external_url = receipt.external_url
    publication.receipt_json = {
        **(publication.receipt_json or {}),
        "provider_receipt": receipt.raw or {},
        "provider_detail": receipt.detail,
    }
    publication.published_at = datetime.now(timezone.utc)
    publication.error_summary = None
    session.commit()
    return {
        "id": publication.id,
        "status": publication.status,
        "channel": publication.channel,
        "external_id": publication.external_id,
        "external_url": publication.external_url,
        "published_at": publication.published_at,
    }
