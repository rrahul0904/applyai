from __future__ import annotations

import logging
import uuid

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.job_source_models import JobSourceDiscovery
from app.jobs.contracts import classify_ingestion_error
from app.jobs.discovery import _register_detected_source, discover_company_career_site, utcnow
from app.jobs.robots import AccessPolicy
from app.jobs.web_security import CrawlBudget, PublicUrlRejected, SafeHttpFetcher


logger = logging.getLogger("applyai.company_discovery")


def process_company_discovery_record(
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
            session.commit()
            try:
                result = discover_company_career_site(record.input_url, fetcher=fetcher)
                record.access_policy = result.access_policy.value
                record.discovered_careers_url = result.careers_url
                record.evidence = [
                    *record.evidence,
                    *result.evidence,
                    *(f"candidate-job-url:{url}" for url in result.candidate_job_urls[:50]),
                ]
                if result.access_policy == AccessPolicy.DISALLOWED:
                    record.status = "BLOCKED"
                    record.error_category = "BLOCKED"
                    record.error_summary = "robots policy disallows company discovery"
                elif result.detection is None or result.careers_url is None:
                    record.status = "REJECTED"
                    record.error_category = "SOURCE_NOT_FOUND"
                    record.error_summary = "No bounded high-confidence career source was found"
                else:
                    detection = result.detection
                    record.detected_provider = detection.provider.value
                    record.confidence = detection.confidence
                    record.resolved_url = result.careers_url
                    record.canonical_url = result.careers_url
                    source = _register_detected_source(
                        session,
                        detection,
                        careers_url=result.careers_url,
                        settings=settings,
                    )
                    source.company_id = record.company_id
                    record.source_registry_id = source.id
                    record.status = (
                        "VERIFIED"
                        if detection.confidence >= settings.career_discovery_min_source_confidence
                        else "DISCOVERED"
                    )
                    record.verified_at = utcnow() if record.status == "VERIFIED" else None
                    logger.info(
                        "career_source_registered",
                        extra={
                            "discovery_id": str(record.id),
                            "source_id": str(source.id),
                            "provider": detection.provider.value,
                        },
                    )
                record.completed_at = utcnow()
                session.commit()
                return record
            except Exception as exc:
                category = classify_ingestion_error(exc)
                record.status = "BLOCKED" if isinstance(exc, PublicUrlRejected) else "FAILED"
                record.error_category = "BLOCKED" if isinstance(exc, PublicUrlRejected) else category.value
                record.error_summary = type(exc).__name__
                record.completed_at = utcnow()
                session.commit()
                logger.warning(
                    "career_discovery_failed",
                    extra={
                        "discovery_id": str(record.id),
                        "error_category": record.error_category,
                    },
                )
                return record
    finally:
        if own_fetcher:
            fetcher.close()
