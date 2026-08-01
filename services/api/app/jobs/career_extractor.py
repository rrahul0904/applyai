from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app.jobs.connectors import html_to_text
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    SourceTrustLevel,
    ValidationStatus,
    canonicalize_public_url,
    normalize_workplace_type,
    validate_raw_job,
)
from app.jobs.jsonld import parse_jobposting_documents, raw_job_from_jsonld


@dataclass(frozen=True)
class CareerExtractionResult:
    status: ValidationStatus
    posting: RawJobPosting | None
    confidence: float
    evidence: tuple[str, ...]


class _CareerHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.in_h1 = False
        self.in_title = False
        self.current_parts: list[str] = []
        self.h1_values: list[str] = []
        self.title_value = ""
        self.links: list[tuple[str, str]] = []
        self.meta: dict[str, str] = {}
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value for key, value in attrs}
        if tag == "h1":
            self.in_h1 = True
            self.current_parts = []
        elif tag == "title":
            self.in_title = True
            self.current_parts = []
        elif tag == "a" and values.get("href"):
            self.links.append((urljoin(self.base_url, str(values["href"])), ""))
        elif tag == "meta" and values.get("content"):
            key = str(values.get("property") or values.get("name") or "").casefold()
            if key:
                self.meta[key] = str(values["content"])

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value:
            return
        self.text_parts.append(value)
        if self.in_h1 or self.in_title:
            self.current_parts.append(value)
        if self.links:
            url, text = self.links[-1]
            # HTMLParser does not expose element nesting directly; appending nearby
            # text is sufficient for conservative apply-link signals.
            if not text:
                self.links[-1] = (url, value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self.in_h1:
            self.h1_values.append(" ".join(self.current_parts).strip())
            self.in_h1 = False
            self.current_parts = []
        elif tag == "title" and self.in_title:
            self.title_value = " ".join(self.current_parts).strip()
            self.in_title = False
            self.current_parts = []


def _apply_links(parser: _CareerHtmlParser) -> list[str]:
    results: list[str] = []
    for url, label in parser.links:
        signal = f"{url} {label}".casefold()
        if any(term in signal for term in ("apply", "application", "submit resume")):
            canonical = canonicalize_public_url(url)
            if canonical and canonical not in results:
                results.append(canonical)
    return results


def _extract_company(parser: _CareerHtmlParser, page_url: str) -> str:
    site_name = parser.meta.get("og:site_name") or parser.meta.get("application-name")
    if site_name:
        return site_name.strip()
    host = (urlsplit(page_url).hostname or "").split(".")
    if len(host) >= 2:
        return host[-2].replace("-", " ").title()
    return ""


def _extract_requisition(text: str) -> str | None:
    patterns = (
        r"(?:requisition|job\s*id|job\s*code|reference)\s*[:#-]?\s*([A-Z0-9_-]{3,40})",
        r"\b(req[-_ ]?[A-Z0-9_-]{3,40})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_career_page(html: str, *, page_url: str) -> CareerExtractionResult:
    jsonld_jobs = parse_jobposting_documents(html)
    if len(jsonld_jobs) == 1:
        posting = raw_job_from_jsonld(jsonld_jobs[0], page_url=page_url)
        validation = validate_raw_job(posting)
        return CareerExtractionResult(
            validation.status,
            posting if validation.accepted else None,
            1.0,
            ("single-jobposting-jsonld", *validation.warnings, *validation.errors),
        )
    if len(jsonld_jobs) > 1:
        return CareerExtractionResult(
            ValidationStatus.QUARANTINED,
            None,
            0.2,
            ("multiple-jobposting-nodes-likely-listing-page",),
        )

    parser = _CareerHtmlParser(page_url)
    parser.feed(html[:4_000_000])
    apply_links = _apply_links(parser)
    body_text = "\n".join(parser.text_parts)
    h1_values = [value for value in parser.h1_values if value]
    requisition = _extract_requisition(body_text)

    if len(apply_links) > 3 and not requisition:
        return CareerExtractionResult(
            ValidationStatus.QUARANTINED,
            None,
            0.15,
            ("multiple-apply-links-likely-listing-page",),
        )
    if len(h1_values) != 1 or len(apply_links) != 1 or len(body_text) < 300:
        return CareerExtractionResult(
            ValidationStatus.QUARANTINED,
            None,
            0.3,
            (
                f"h1-count:{len(h1_values)}",
                f"apply-link-count:{len(apply_links)}",
                f"text-length:{len(body_text)}",
            ),
        )

    title = h1_values[0]
    company = _extract_company(parser, page_url)
    location_match = re.search(
        r"(?:location|work location)\s*[:\-]\s*([^\n|]{2,120})",
        body_text,
        flags=re.IGNORECASE,
    )
    location = location_match.group(1).strip() if location_match else None
    workplace = normalize_workplace_type(None, (location,) if location else ())
    identifier = requisition or hashlib.sha256(page_url.encode()).hexdigest()[:24]
    source_url = canonicalize_public_url(page_url) or page_url
    posting = RawJobPosting(
        source_type=JobSourceType.CAREER_SITE,
        source_name="career-site",
        source_company_identity=(urlsplit(page_url).hostname or company).casefold(),
        source_job_identity=f"{urlsplit(page_url).hostname}:{identifier}",
        external_job_id=f"{urlsplit(page_url).hostname}:{identifier}",
        internal_job_id=requisition,
        source_url=source_url,
        apply_url=apply_links[0],
        company_name=company,
        title=title,
        description=html_to_text(html),
        location_text=location,
        locations=(location,) if location else (),
        workplace_type=workplace,
        fetched_at=datetime.now(timezone.utc),
        raw_payload={
            "source_url": source_url,
            "apply_url": apply_links[0],
            "title": title,
            "company_name": company,
            "requisition": requisition,
            "extraction": "CONSERVATIVE_GENERIC_HTML",
        },
        source_metadata={
            "trust_level": SourceTrustLevel.EMPLOYER_CAREER_SITE.value,
            "generic_extraction": True,
        },
    )
    validation = validate_raw_job(posting)
    if not validation.accepted:
        return CareerExtractionResult(
            ValidationStatus.QUARANTINED,
            None,
            0.45,
            ("generic-validation-failed", *validation.errors, *validation.warnings),
        )
    return CareerExtractionResult(
        ValidationStatus.VALID_WITH_WARNINGS,
        posting,
        0.72,
        (
            "single-h1",
            "single-apply-link",
            "substantial-job-specific-content",
            "requisition-present" if requisition else "url-derived-identity",
        ),
    )
