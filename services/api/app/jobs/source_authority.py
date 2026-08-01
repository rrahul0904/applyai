from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.job_quality_models import JobFieldProvenance
from app.job_source_models import JobSourceRegistry
from app.models import Job, JobCompensation, JobLocation, JobSource, JobSourceLink


_TRUST_RANK = {
    "EMPLOYER_DIRECT": 700,
    "OFFICIAL_ATS": 600,
    "EMPLOYER_CAREER_SITE": 500,
    "LICENSED_FEED": 400,
    "STRUCTURED_JOB_PAGE": 350,
    "THIRD_PARTY_SOURCE": 200,
    "UNVERIFIED": 100,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _registry_for_source(session: Session, source: JobSource) -> JobSourceRegistry | None:
    registry_id = (source.checkpoint or {}).get("source_registry_id")
    if not registry_id:
        return None
    try:
        return session.get(JobSourceRegistry, registry_id)
    except Exception:
        return None


def source_authority_score(session: Session, link: JobSourceLink) -> tuple[int, float, str]:
    source = session.get(JobSource, link.job_source_id)
    if source is None:
        return (0, 0.0, "missing-source")
    checkpoint = dict(source.checkpoint or {})
    registry = _registry_for_source(session, source)
    trust = (
        registry.trust_level
        if registry is not None
        else str((checkpoint.get("source_metadata") or {}).get("trust_level") or "UNVERIFIED")
    )
    rank = _TRUST_RANK.get(trust, 0)
    if source.source_url.startswith("https://"):
        rank += 20
    if checkpoint.get("validation_status") in {"VALID", "VALID_WITH_WARNINGS", "NORMALIZED"}:
        rank += 10
    if checkpoint.get("confirmed_closed"):
        rank -= 500
    freshness = source.last_seen_at.timestamp() if source.last_seen_at else 0.0
    return (rank, freshness, trust)


def choose_primary_source_link(session: Session, job_id) -> JobSourceLink | None:
    links = list(
        session.scalars(
            select(JobSourceLink).where(JobSourceLink.job_id == job_id)
        )
    )
    if not links:
        return None
    selected = max(links, key=lambda link: source_authority_score(session, link))
    for link in links:
        link.is_primary = link.id == selected.id
    return selected


def should_source_update_canonical(session: Session, job_id, job_source_id) -> bool:
    selected = choose_primary_source_link(session, job_id)
    return selected is not None and selected.job_source_id == job_source_id


def _hash(value: object) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()


def record_field_provenance(session: Session, job_id) -> None:
    selected = choose_primary_source_link(session, job_id)
    job = session.get(Job, job_id)
    if selected is None or job is None:
        return
    source = session.get(JobSource, selected.job_source_id)
    _, _, trust = source_authority_score(session, selected)
    location = session.scalar(
        select(JobLocation).where(JobLocation.job_id == job_id).order_by(JobLocation.id).limit(1)
    )
    compensation = session.scalar(
        select(JobCompensation)
        .where(JobCompensation.job_id == job_id)
        .order_by(JobCompensation.id)
        .limit(1)
    )
    values = {
        "title": job.title,
        "description": job.description,
        "location": f"{location.location_text}|{location.work_mode}" if location else "",
        "employment_type": job.employment_type,
        "seniority": job.seniority,
        "compensation": (
            f"{compensation.minimum}|{compensation.maximum}|{compensation.provenance}"
            if compensation
            else ""
        ),
        "apply_url": source.source_url if source else "",
    }
    session.execute(delete(JobFieldProvenance).where(JobFieldProvenance.job_id == job_id))
    session.add_all(
        [
            JobFieldProvenance(
                job_id=job_id,
                field_name=field_name,
                job_source_link_id=selected.id,
                value_hash=_hash(value),
                selection_reason=f"PRIMARY_SOURCE_AUTHORITY:{trust}",
                selected_at=utcnow(),
            )
            for field_name, value in values.items()
        ]
    )
