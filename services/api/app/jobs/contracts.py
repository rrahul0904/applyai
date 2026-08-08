from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class JobSourceType(StrEnum):
    GREENHOUSE = "GREENHOUSE"
    LEVER = "LEVER"
    ASHBY = "ASHBY"
    SMARTRECRUITERS = "SMARTRECRUITERS"
    WORKABLE = "WORKABLE"
    WORKDAY = "WORKDAY"
    ICIMS = "ICIMS"
    ORACLE = "ORACLE"
    SUCCESSFACTORS = "SUCCESSFACTORS"
    CAREER_SITE = "CAREER_SITE"
    JSON_LD = "JSON_LD"
    XML_FEED = "XML_FEED"
    JSON_FEED = "JSON_FEED"
    USAJOBS = "USAJOBS"
    RELIEFWEB = "RELIEFWEB"
    GOVERNMENT_FEED = "GOVERNMENT_FEED"
    AUTHORIZED_AGGREGATOR_FEED = "AUTHORIZED_AGGREGATOR_FEED"
    USER_SUBMITTED_URL = "USER_SUBMITTED_URL"
    EMPLOYER_DIRECT = "EMPLOYER_DIRECT"
    DEVELOPMENT_SEED = "DEVELOPMENT_SEED"


class SourceTrustLevel(StrEnum):
    APPLYAI_FIRST_PARTY = "APPLYAI_FIRST_PARTY"
    EMPLOYER_DIRECT = "EMPLOYER_DIRECT"
    EMPLOYER_OFFICIAL_API = "EMPLOYER_OFFICIAL_API"
    OFFICIAL_ATS = "OFFICIAL_ATS"
    EMPLOYER_JSONLD = "EMPLOYER_JSONLD"
    EMPLOYER_CAREER_SITE = "EMPLOYER_CAREER_SITE"
    GOVERNMENT_OFFICIAL = "GOVERNMENT_OFFICIAL"
    AUTHORIZED_AGGREGATOR_FEED = "AUTHORIZED_AGGREGATOR_FEED"
    LICENSED_FEED = "LICENSED_FEED"
    STRUCTURED_JOB_PAGE = "STRUCTURED_JOB_PAGE"
    VERIFIED_PARTNER = "VERIFIED_PARTNER"
    THIRD_PARTY_SOURCE = "THIRD_PARTY_SOURCE"
    CANDIDATE_IMPORTED = "CANDIDATE_IMPORTED"
    UNVERIFIED_PUBLIC_SOURCE = "UNVERIFIED_PUBLIC_SOURCE"
    UNVERIFIED = "UNVERIFIED"


class SourceHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILING = "FAILING"
    DISABLED = "DISABLED"
    BLOCKED = "BLOCKED"


class ValidationStatus(StrEnum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INVALID = "INVALID"
    QUARANTINED = "QUARANTINED"


class IngestionErrorCategory(StrEnum):
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    PARSER_ERROR = "PARSER_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    BLOCKED = "BLOCKED"
    CONFIG_ERROR = "CONFIG_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    UNKNOWN = "UNKNOWN"


class DedupReason(StrEnum):
    EXACT_SOURCE_ID = "EXACT_SOURCE_ID"
    EXACT_APPLY_URL = "EXACT_APPLY_URL"
    INTERNAL_REQUISITION_ID = "INTERNAL_REQUISITION_ID"
    CONTENT_FINGERPRINT = "CONTENT_FINGERPRINT"
    HEURISTIC_MATCH = "HEURISTIC_MATCH"
    NEW_CANONICAL_JOB = "NEW_CANONICAL_JOB"


@dataclass(frozen=True)
class SourceDiscoveryResult:
    source_type: JobSourceType
    source_identity: str
    source_url: str
    confidence: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawJobPosting:
    source_type: JobSourceType
    source_name: str
    source_company_identity: str
    source_job_identity: str
    external_job_id: str
    company_name: str
    title: str
    description: str
    source_url: str
    apply_url: str
    internal_job_id: str | None = None
    company_domain: str | None = None
    location_text: str | None = None
    locations: tuple[str, ...] = ()
    employment_type: str = "UNKNOWN"
    workplace_type: str = "UNKNOWN"
    seniority: str = "UNKNOWN"
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    salary_provenance: str | None = None
    date_posted: datetime | None = None
    valid_through: datetime | None = None
    source_updated_at: datetime | None = None
    fetched_at: datetime | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    source_metadata: dict[str, Any] = field(default_factory=dict)
    skills: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.status in {
            ValidationStatus.VALID,
            ValidationStatus.VALID_WITH_WARNINGS,
        }


_SAFE_TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gh_src",
    "source",
    "ref",
    "referrer",
}


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_title(value: str) -> str:
    title = normalize_text(value)
    title = re.sub(r"\bsr(?:\.|\b)", "senior", title)
    title = re.sub(r"\bjr(?:\.|\b)", "junior", title)
    title = re.sub(r"\s*,\s*senior$", " senior", title)
    return " ".join(title.split())


def normalize_employment_type(value: str | None) -> str:
    normalized = normalize_text(value or "")
    mapping = {
        "full time": "FULL_TIME",
        "full-time": "FULL_TIME",
        "fulltime": "FULL_TIME",
        "part time": "PART_TIME",
        "part-time": "PART_TIME",
        "parttime": "PART_TIME",
        "contract": "CONTRACT",
        "contractor": "CONTRACT",
        "temporary": "TEMPORARY",
        "temp": "TEMPORARY",
        "intern": "INTERNSHIP",
        "internship": "INTERNSHIP",
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized.upper() in {
        "FULL_TIME",
        "PART_TIME",
        "CONTRACT",
        "TEMPORARY",
        "INTERNSHIP",
        "OTHER",
        "UNKNOWN",
    }:
        return normalized.upper()
    return "UNKNOWN" if not normalized else "OTHER"


def normalize_workplace_type(value: str | None, locations: tuple[str, ...] = ()) -> str:
    normalized = normalize_text(value or "")
    if normalized in {"remote", "REMOTE".casefold()}:
        return "REMOTE"
    if normalized in {"hybrid", "HYBRID".casefold()}:
        return "HYBRID"
    if normalized in {"on-site", "onsite", "on site"}:
        return "ONSITE"
    combined = " ".join(locations).casefold()
    if "remote" in combined:
        return "REMOTE"
    if "hybrid" in combined:
        return "HYBRID"
    return "UNKNOWN"


def canonicalize_public_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.hostname.casefold() if parsed.hostname else ""
    port = parsed.port
    netloc = host
    if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in _SAFE_TRACKING_PARAMETERS
        ],
        doseq=True,
    )
    return urlunsplit((parsed.scheme.casefold(), netloc, path, query, ""))


def validate_raw_job(posting: RawJobPosting) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    title = posting.title.strip()
    description = posting.description.strip()

    if not title or title in {"-", "n/a", "unknown"}:
        errors.append("TITLE_MISSING_OR_PLACEHOLDER")
    if not posting.company_name.strip():
        errors.append("COMPANY_MISSING")
    if len(description) < 40:
        errors.append("DESCRIPTION_TOO_SHORT")
    if canonicalize_public_url(posting.source_url) is None:
        errors.append("SOURCE_URL_INVALID")
    if canonicalize_public_url(posting.apply_url) is None:
        errors.append("APPLY_URL_INVALID")
    if not posting.external_job_id.strip() or not posting.source_job_identity.strip():
        errors.append("SOURCE_IDENTITY_MISSING")
    if not posting.locations and not posting.location_text:
        warnings.append("LOCATION_UNSPECIFIED")
    if posting.salary_min is not None and posting.salary_max is not None:
        if posting.salary_min > posting.salary_max:
            errors.append("SALARY_RANGE_INVALID")
    if errors:
        return ValidationResult(ValidationStatus.INVALID, tuple(errors), tuple(warnings))
    if warnings:
        return ValidationResult(
            ValidationStatus.VALID_WITH_WARNINGS,
            (),
            tuple(warnings),
        )
    return ValidationResult(ValidationStatus.VALID)


def classify_ingestion_error(exc: Exception) -> IngestionErrorCategory:
    name = type(exc).__name__.casefold()
    message = str(exc).casefold()
    if "timeout" in name or "timeout" in message:
        return IngestionErrorCategory.TIMEOUT
    if "429" in message or "rate" in message:
        return IngestionErrorCategory.RATE_LIMITED
    if "401" in message or "403" in message or "auth" in message:
        return IngestionErrorCategory.AUTH_REQUIRED
    if "404" in message or "not found" in message:
        return IngestionErrorCategory.SOURCE_NOT_FOUND
    if "connect" in name or "network" in message:
        return IngestionErrorCategory.NETWORK
    if isinstance(exc, (KeyError, TypeError, ValueError)):
        return IngestionErrorCategory.INVALID_RESPONSE
    return IngestionErrorCategory.UNKNOWN
