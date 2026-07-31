from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.job_source_models import JobSourceDiscovery, JobSourceRegistry
from app.jobs.adapters import normalized_from_raw
from app.jobs.ats_detector import ATSDetection, detect_ats
from app.jobs.career_extractor import CareerExtractionResult, extract_career_page
from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    SourceHealthStatus,
    SourceTrustLevel,
    ValidationStatus,
    canonicalize_public_url,
    classify_ingestion_error,
)
from app.jobs.registry import upsert_source
from app.jobs.robots import AccessPolicy, evaluate_robots
from app.jobs.sitemaps import discover_job_urls_from_sitemaps
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline
from app.jobs.web_security import CrawlBudget, PublicUrlRejected, SafeHttpFetcher, validate_public_http_url
from app.models import JobSource, JobSourceLink


logger = logging.getLogger("applyai.career_discovery")

COMMON_CAREER_PATHS = (
    "/careers",
    "/jobs",
    "/careers/jobs",
    "/company/careers",
    "/work-with-us",
    "/join-us",
)
SEMANTIC_LINK_TERMS = (
    "careers",
    "jobs",
    "join our team",
    "work with us",
    "open positions",
    "open roles",
)


@dataclass(frozen=True)
class CompanyDiscoveryResult:
    careers_url: str | None
    detection: ATSDetection | None
    candidate_job_urls: tuple[str, ...]
    evidence: tuple[str, ...]
    access_policy: AccessPolicy


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        if values.get("href"):
            self._current_href = urljoin(self.base_url, str(values["href"]))
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            value = " ".join(data.split())
            if value:
                self._current_text.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href:
            self.links.append((self._current_href, " ".join(self._current_text)))
            self._current_href = None
            self._current_text = []


class StaticRawJobConnector(JobSourceConnector):
    def __init__(self, posting: RawJobPosting) -> None:
        self.posting = posting
        self.key = posting.source_name

    def source_company_identity(self) -> str:
        return self.posting.source_company_identity

    def fetch(self, checkpoint):
        del checkpoint
        return [dict(self.posting.raw_payload)]

    def to_raw(self, payload: dict) -> RawJobPosting:
        del payload
        return self.posting

    def normalize(self, payload: dict) -> NormalizedJob:
        del payload
        return normalized_from_raw(self.posting)

    def checkpoint(self):
        return {"count": 1}

    def health(self):
        return ConnectorHealth(True, datetime.now(timezone.utc), "Imported public job page")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def request_key_for(user_id: uuid.UUID | None, canonical_url: str) -> str:
    material = f"{user_id or 'system'}:{canonical_url}".encode()
    return hashlib.sha256(material).hexdigest()


def _root_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))


def _semantic_links(html: str, base_url: str) -> list[str]:
    parser = _LinkParser(base_url)
    parser.feed(html[:2_000_000])
    results: list[str] = []
    base_host = urlsplit(base_url).hostname
    for url, label in parser.links:
        text = f"{url} {label}".casefold()
        if not any(term in text for term in SEMANTIC_LINK_TERMS):
            continue
        if urlsplit(url).hostname != base_host and not any(
            provider in text
            for provider in ("greenhouse", "lever.co", "ashbyhq", "workday", "smartrecruiters", "workable")
        ):
            continue
        canonical = canonicalize_public_url(url)
        if canonical and canonical not in results:
            results.append(canonical)
    return results


def discover_company_career_site(
    input_url: str,
    *,
    fetcher: SafeHttpFetcher,
) -> CompanyDiscoveryResult:
    root = _root_url(validate_public_http_url(input_url, resolver=fetcher.resolver))
    robots = evaluate_robots(fetcher, root)
    if robots.policy == AccessPolicy.DISALLOWED:
        return CompanyDiscoveryResult(None, None, (), (robots.detail,), robots.policy)

    evidence: list[str] = [f"robots:{robots.policy.value}"]
    candidates: list[str] = []
    homepage_html = ""
    try:
        homepage = fetcher.fetch(root)
        if homepage.status_code < 400:
            homepage_html = homepage.text
            candidates.extend(_semantic_links(homepage_html, homepage.final_url))
    except Exception as exc:
        evidence.append(f"homepage:{type(exc).__name__}")

    for path in COMMON_CAREER_PATHS:
        candidate = urljoin(root, path)
        if candidate not in candidates:
            candidates.append(candidate)

    best: tuple[float, str, ATSDetection, str] | None = None
    robots_text = None
    try:
        robots_result = fetcher.fetch(urljoin(root, "/robots.txt"), accept="text/plain")
        if robots_result.status_code < 400:
            robots_text = robots_result.text
    except Exception:
        pass

    for candidate in candidates:
        if fetcher.pages_fetched >= fetcher.budget.max_pages:
            break
        try:
            result = fetcher.fetch(candidate)
        except Exception as exc:
            evidence.append(f"candidate:{candidate}:{type(exc).__name__}")
            continue
        if result.status_code >= 400:
            continue
        detection = detect_ats(result.final_url, result.text)
        score = detection.confidence
        if any(term in result.final_url.casefold() for term in ("career", "job", "position", "opening")):
            score = min(1.0, score + 0.08)
        if best is None or score > best[0]:
            best = (score, result.final_url, detection, result.text)

    sitemap_urls: tuple[str, ...] = ()
    if fetcher.pages_fetched < fetcher.budget.max_pages:
        sitemap_result = discover_job_urls_from_sitemaps(
            fetcher,
            root,
            robots_text=robots_text,
            max_sitemaps=max(1, min(3, fetcher.budget.max_pages - fetcher.pages_fetched)),
            max_job_urls=500,
        )
        sitemap_urls = sitemap_result.candidate_job_urls
        evidence.extend(f"sitemap:{url}" for url in sitemap_result.sitemap_urls)

    if best is None:
        return CompanyDiscoveryResult(None, None, sitemap_urls, tuple(evidence), robots.policy)
    _, careers_url, detection, _ = best
    return CompanyDiscoveryResult(
        careers_url,
        detection,
        sitemap_urls,
        tuple([*evidence, *detection.evidence]),
        robots.policy,
    )


def _register_detected_source(
    session: Session,
    detection: ATSDetection,
    *,
    careers_url: str,
    settings: Settings,
) -> JobSourceRegistry:
    supported = detection.provider in {
        JobSourceType.GREENHOUSE,
        JobSourceType.LEVER,
        JobSourceType.ASHBY,
    }
    configuration: dict = {}
    if detection.provider == JobSourceType.GREENHOUSE:
        configuration["board_token"] = detection.source_identity
    elif detection.provider == JobSourceType.LEVER:
        configuration["site"] = detection.source_identity
    elif detection.provider == JobSourceType.ASHBY:
        configuration["board_name"] = detection.source_identity
        configuration["include_compensation"] = True
    else:
        configuration["detected_provider"] = detection.provider.value
        configuration["detection_evidence"] = list(detection.evidence)

    source = upsert_source(
        session,
        source_type=detection.provider,
        source_name=f"Discovered {detection.provider.value}: {detection.source_identity}",
        source_identity=detection.source_identity,
        base_url=detection.candidate_source_url,
        configuration=configuration,
        interval_seconds=settings.job_source_default_interval_seconds,
        trust_level=(
            SourceTrustLevel.OFFICIAL_ATS
            if supported
            else SourceTrustLevel.EMPLOYER_CAREER_SITE
        ),
    )
    source.careers_url = careers_url
    source.enabled = supported
    source.crawl_allowed = True
    if not supported:
        source.health_status = SourceHealthStatus.DISABLED.value
    session.flush()
    return source


def _existing_job_id(session: Session, canonical_url: str) -> uuid.UUID | None:
    return session.scalar(
        select(JobSourceLink.job_id)
        .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
        .where(
            (JobSource.source_url == canonical_url)
            | (JobSource.checkpoint["canonical_apply_url"].astext == canonical_url)
        )
        .order_by(JobSourceLink.is_primary.desc())
        .limit(1)
    )


def process_discovery_record(
    discovery_id: uuid.UUID,
    *,
    settings: Settings | None = None,
    fetcher: SafeHttpFetcher | None = None,
) -> JobSourceDiscovery:
    settings = settings or get_settings()
    own_fetcher = fetcher is None
    fetcher = fetcher or SafeHttpFetcher(
        budget=CrawlBudget(
            max_pages=settings.career_discovery_max_pages,
            max_response_bytes=settings.career_discovery_max_bytes,
            max_redirects=settings.career_discovery_max_redirects,
            request_timeout_seconds=settings.career_discovery_timeout_seconds,
        )
    )
    try:
        with SessionLocal() as session:
            record = session.get(JobSourceDiscovery, discovery_id)
            if record is None:
                raise LookupError(f"Discovery {discovery_id} does not exist")
            if record.status == "VERIFIED":
                return record
            record.status = "FETCHING"
            record.attempt_count += 1
            record.error_category = None
            record.error_summary = None
            session.commit()

            try:
                canonical_input = validate_public_http_url(record.input_url, resolver=fetcher.resolver)
                robots = evaluate_robots(fetcher, canonical_input)
                record.access_policy = robots.policy.value
                record.evidence = [*record.evidence, robots.detail]
                if robots.policy == AccessPolicy.DISALLOWED:
                    record.status = "BLOCKED"
                    record.error_category = "BLOCKED"
                    record.error_summary = "robots policy disallows the submitted URL"
                    record.completed_at = utcnow()
                    session.commit()
                    logger.info("career_discovery_blocked", extra={"discovery_id": str(record.id)})
                    return record
                if robots.policy == AccessPolicy.MANUAL_REVIEW:
                    record.status = "BLOCKED"
                    record.error_category = "BLOCKED"
                    record.error_summary = "source requires manual access-policy review"
                    record.completed_at = utcnow()
                    session.commit()
                    return record

                result = fetcher.fetch(
                    canonical_input,
                    etag=record.etag,
                    last_modified=record.last_modified,
                )
                record.discovered_url = canonical_input
                record.resolved_url = result.final_url
                record.canonical_url = canonicalize_public_url(result.final_url)
                record.etag = result.etag
                record.last_modified = result.last_modified
                record.content_hash = result.content_hash
                if result.status_code == 304:
                    record.status = "VERIFIED" if record.job_id else "DISCOVERED"
                    record.verified_at = utcnow()
                    record.completed_at = utcnow()
                    session.commit()
                    return record
                if result.status_code >= 400:
                    raise RuntimeError(f"Public job page returned HTTP {result.status_code}")

                canonical_url = record.canonical_url or canonical_input
                existing_job_id = _existing_job_id(session, canonical_url)
                if existing_job_id is not None:
                    record.job_id = existing_job_id
                    record.status = "VERIFIED"
                    record.verified_at = utcnow()
                    record.completed_at = utcnow()
                    session.commit()
                    return record

                detection = detect_ats(result.final_url, result.text)
                record.detected_provider = detection.provider.value
                record.confidence = detection.confidence
                record.evidence = [*record.evidence, *detection.evidence]
                source = _register_detected_source(
                    session,
                    detection,
                    careers_url=result.final_url,
                    settings=settings,
                )
                record.source_registry_id = source.id

                extraction = extract_career_page(result.text, page_url=result.final_url)
                record.evidence = [*record.evidence, *extraction.evidence]
                if extraction.posting is None:
                    record.status = (
                        "DISCOVERED"
                        if detection.confidence >= settings.career_discovery_min_source_confidence
                        else "REJECTED"
                    )
                    record.completed_at = utcnow()
                    session.commit()
                    logger.info(
                        "career_source_detected",
                        extra={
                            "discovery_id": str(record.id),
                            "provider": detection.provider.value,
                            "confidence": detection.confidence,
                        },
                    )
                    return record

                posting = extraction.posting
                record.apply_url = posting.apply_url
                submitted_identity = hashlib.sha256(canonical_url.encode()).hexdigest()
                submitted_source = upsert_source(
                    session,
                    source_type=JobSourceType.USER_SUBMITTED_URL,
                    source_name=f"User-submitted job: {urlsplit(canonical_url).hostname}",
                    source_identity=submitted_identity,
                    base_url=canonical_url,
                    configuration={
                        "canonical_url": canonical_url,
                        "detected_provider": detection.provider.value,
                        "discovery_id": str(record.id),
                    },
                    interval_seconds=settings.career_discovery_refresh_interval_seconds,
                    trust_level=(
                        SourceTrustLevel.STRUCTURED_JOB_PAGE
                        if posting.source_type == JobSourceType.JSON_LD
                        else SourceTrustLevel.EMPLOYER_CAREER_SITE
                    ),
                )
                submitted_source.enabled = False
                submitted_source.crawl_allowed = robots.policy == AccessPolicy.ALLOWED
                submitted_source.health_status = SourceHealthStatus.DISABLED.value
                session.commit()

                counts = RegisteredSourceIngestionPipeline(session).run(
                    submitted_source,
                    StaticRawJobConnector(posting),
                )
                job_id = session.scalar(
                    select(JobSourceLink.job_id)
                    .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
                    .where(
                        JobSource.connector_key == posting.source_name,
                        JobSource.external_job_id == posting.external_job_id,
                    )
                    .limit(1)
                )
                if job_id is None or counts["valid"] != 1:
                    raise RuntimeError("Extracted job did not produce a canonical job")
                record.job_id = job_id
                record.status = "VERIFIED"
                record.verified_at = utcnow()
                record.completed_at = utcnow()
                session.commit()
                logger.info(
                    "job_url_imported",
                    extra={
                        "discovery_id": str(record.id),
                        "job_id": str(job_id),
                        "provider": detection.provider.value,
                    },
                )
                return record
            except Exception as exc:
                category = classify_ingestion_error(exc)
                record.status = "BLOCKED" if isinstance(exc, PublicUrlRejected) else "FAILED"
                record.error_category = "BLOCKED" if isinstance(exc, PublicUrlRejected) else category.value
                record.error_summary = type(exc).__name__
                record.completed_at = utcnow()
                session.commit()
                logger.warning(
                    "job_url_rejected" if record.status == "BLOCKED" else "career_discovery_failed",
                    extra={
                        "discovery_id": str(record.id),
                        "error_category": record.error_category,
                    },
                )
                return record
    finally:
        if own_fetcher:
            fetcher.close()
