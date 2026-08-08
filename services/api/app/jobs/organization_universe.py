from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.global_job_supply_models import OrganizationProfile
from app.models import Company, CompanyAlias


ORGANIZATION_TYPES = {
    "COMPANY",
    "STARTUP",
    "UNIVERSITY",
    "COLLEGE",
    "RESEARCH_INSTITUTE",
    "HOSPITAL",
    "HEALTH_SYSTEM",
    "NONPROFIT",
    "NGO",
    "FOUNDATION",
    "GOVERNMENT",
    "PUBLIC_INSTITUTION",
    "NATIONAL_LAB",
}

SOURCE_STATES = {
    "NEW",
    "DISCOVERING",
    "DISCOVERED",
    "VERIFIED",
    "ACTIVE",
    "BLOCKED",
    "FAILED",
    "REQUIRES_REVIEW",
}


@dataclass(frozen=True)
class OrganizationRecord:
    canonical_name: str
    domain: str | None = None
    aliases: tuple[str, ...] = ()
    organization_type: str = "COMPANY"
    industry: str | None = None
    country_code: str | None = None
    state_region: str | None = None
    size_band: str | None = None
    priority: int = 50
    careers_url: str | None = None
    ats_provider: str | None = None
    dataset: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().casefold()
    if not candidate:
        return None
    parsed = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
    host = (parsed.hostname or "").strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or len(host) > 255 or not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ValueError(f"Invalid organization domain: {value}")
    return host


def _clean_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"Invalid public URL: {value}")
    return value.strip()


def validate_record(record: OrganizationRecord) -> OrganizationRecord:
    name = " ".join(record.canonical_name.split()).strip()
    if len(name) < 2 or len(name) > 240:
        raise ValueError("canonical_name must contain 2-240 characters")
    organization_type = record.organization_type.upper().strip()
    if organization_type not in ORGANIZATION_TYPES:
        raise ValueError(f"Unsupported organization_type: {record.organization_type}")
    country_code = record.country_code.upper().strip() if record.country_code else None
    if country_code and len(country_code) != 2:
        raise ValueError("country_code must be ISO alpha-2")
    priority = max(0, min(int(record.priority), 100))
    return OrganizationRecord(
        canonical_name=name,
        domain=normalize_domain(record.domain),
        aliases=tuple(sorted({" ".join(alias.split()).strip() for alias in record.aliases if alias.strip()})),
        organization_type=organization_type,
        industry=record.industry.strip() if record.industry else None,
        country_code=country_code,
        state_region=record.state_region.strip() if record.state_region else None,
        size_band=record.size_band.strip() if record.size_band else None,
        priority=priority,
        careers_url=_clean_url(record.careers_url),
        ats_provider=record.ats_provider.upper().strip() if record.ats_provider else None,
        dataset=record.dataset.strip() if record.dataset else None,
        metadata=dict(record.metadata or {}),
    )


def upsert_organization(session: Session, incoming: OrganizationRecord) -> tuple[Company, OrganizationProfile, str]:
    record = validate_record(incoming)
    profile = None
    company = None

    if record.domain:
        profile = session.scalar(
            select(OrganizationProfile).where(OrganizationProfile.canonical_domain == record.domain)
        )
        if profile is not None:
            company = session.get(Company, profile.company_id)

    if company is None:
        company = session.scalar(
            select(Company).where(Company.normalized_name == normalize_name(record.canonical_name))
        )

    created = False
    if company is None:
        company = Company(
            canonical_name=record.canonical_name,
            normalized_name=normalize_name(record.canonical_name),
            website_url=f"https://{record.domain}" if record.domain else None,
        )
        session.add(company)
        session.flush()
        created = True
    elif record.domain and not company.website_url:
        company.website_url = f"https://{record.domain}"

    if profile is None:
        profile = session.scalar(
            select(OrganizationProfile).where(OrganizationProfile.company_id == company.id)
        )
    if profile is None:
        profile = OrganizationProfile(company_id=company.id)
        session.add(profile)

    # Conflicting non-null domains require review rather than silently merging two organizations.
    if profile.canonical_domain and record.domain and profile.canonical_domain != record.domain:
        profile.source_status = "REQUIRES_REVIEW"
        profile.metadata_json = {
            **dict(profile.metadata_json or {}),
            "domain_conflict": [profile.canonical_domain, record.domain],
        }
    elif record.domain:
        profile.canonical_domain = record.domain

    profile.organization_type = record.organization_type
    profile.industry = record.industry or profile.industry
    profile.country_code = record.country_code or profile.country_code
    profile.state_region = record.state_region or profile.state_region
    profile.size_band = record.size_band or profile.size_band
    profile.priority = max(int(profile.priority or 0), record.priority)
    profile.careers_url = record.careers_url or profile.careers_url
    profile.ats_provider = record.ats_provider or profile.ats_provider
    if profile.source_status not in {"REQUIRES_REVIEW", "BLOCKED"}:
        profile.source_status = profile.source_status or "NEW"
    profile.metadata_json = {**dict(profile.metadata_json or {}), **record.metadata}
    provenance = list(profile.dataset_provenance or [])
    if record.dataset and record.dataset not in provenance:
        provenance.append(record.dataset)
    profile.dataset_provenance = provenance

    aliases = {record.canonical_name, *record.aliases}
    for alias in aliases:
        normalized = normalize_name(alias)
        exists = session.scalar(
            select(CompanyAlias).where(
                CompanyAlias.company_id == company.id,
                CompanyAlias.normalized_alias == normalized,
            )
        )
        if exists is None and normalized != company.normalized_name:
            session.add(CompanyAlias(company_id=company.id, alias=alias, normalized_alias=normalized))

    session.flush()
    return company, profile, "created" if created else "updated"


def import_organizations(session: Session, records: Iterable[OrganizationRecord]) -> dict[str, int]:
    counts = {"created": 0, "updated": 0, "failed": 0}
    for record in records:
        try:
            # One malformed/conflicting record must not undo previously accepted rows.
            with session.begin_nested():
                _, _, result = upsert_organization(session, record)
                counts[result] += 1
        except Exception:
            counts["failed"] += 1
    session.commit()
    return counts


def _record_from_mapping(item: dict[str, Any], *, dataset: str | None = None) -> OrganizationRecord:
    aliases = item.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [value.strip() for value in aliases.split("|") if value.strip()]
    metadata = item.get("metadata") or item.get("metadata_json") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata) if metadata.strip() else {}
        except json.JSONDecodeError:
            metadata = {"source_metadata_text": metadata}
    return OrganizationRecord(
        canonical_name=str(item.get("canonical_name") or item.get("name") or ""),
        domain=item.get("domain") or item.get("canonical_domain"),
        aliases=tuple(str(value) for value in aliases),
        organization_type=str(item.get("organization_type") or item.get("type") or "COMPANY"),
        industry=item.get("industry"),
        country_code=item.get("country_code") or item.get("country"),
        state_region=item.get("state_region") or item.get("region"),
        size_band=item.get("size_band"),
        priority=int(item.get("priority") or 50),
        careers_url=item.get("careers_url"),
        ats_provider=item.get("ats_provider"),
        dataset=str(item.get("dataset") or dataset or "") or None,
        metadata=dict(metadata),
    )


def load_organization_records(path: str | Path, *, dataset: str | None = None) -> list[OrganizationRecord]:
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            return [_record_from_mapping(dict(row), dataset=dataset) for row in csv.DictReader(handle)]
    if suffix == ".jsonl":
        rows = []
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(_record_from_mapping(json.loads(line), dataset=dataset))
        return rows
    if suffix == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("organizations") or payload.get("data") or []
        if not isinstance(payload, list):
            raise ValueError("JSON organization file must be a list or contain organizations/data list")
        return [_record_from_mapping(dict(item), dataset=dataset) for item in payload]
    raise ValueError("Organization imports support .csv, .json and .jsonl")
