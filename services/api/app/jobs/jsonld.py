from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit

from app.jobs.connectors import html_to_text
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    SourceTrustLevel,
    canonicalize_public_url,
    normalize_employment_type,
    normalize_workplace_type,
)


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._parts: list[str] = []
        self.documents: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        values = {key.casefold(): value for key, value in attrs}
        script_type = str(values.get("type") or "").casefold().split(";", 1)[0].strip()
        if script_type == "application/ld+json":
            self._capture = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture:
            self.documents.append("".join(self._parts).strip())
            self._capture = False
            self._parts = []


def _nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if graph is not None:
            yield from _nodes(graph)
    elif isinstance(value, list):
        for item in value:
            yield from _nodes(item)


def _is_job_posting(node: dict[str, Any]) -> bool:
    value = node.get("@type")
    if isinstance(value, list):
        return any(str(item).casefold() == "jobposting" for item in value)
    return str(value or "").casefold() == "jobposting"


def parse_jobposting_documents(html: str) -> list[dict[str, Any]]:
    parser = _JsonLdParser()
    parser.feed(html[:4_000_000])
    results: list[dict[str, Any]] = []
    for document in parser.documents:
        if not document:
            continue
        try:
            payload = json.loads(document)
        except json.JSONDecodeError:
            continue
        for node in _nodes(payload):
            if _is_job_posting(node):
                results.append(node)
    return results


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("name", "value", "valueReference", "addressLocality"):
            if value.get(key) not in {None, ""}:
                nested = _string_value(value[key])
                if nested:
                    return nested
        return None
    if isinstance(value, list):
        values = [item for item in (_string_value(item) for item in value) if item]
        return ", ".join(values) if values else None
    text = str(value).strip()
    return text or None


def _organization(node: dict[str, Any]) -> tuple[str, str | None]:
    organization = node.get("hiringOrganization")
    if not isinstance(organization, dict):
        return "", None
    name = str(organization.get("name") or "").strip()
    same_as = organization.get("sameAs") or organization.get("url")
    domain = None
    if same_as:
        domain = urlsplit(str(same_as)).hostname
    return name, domain.casefold() if domain else None


def _locations(node: dict[str, Any]) -> tuple[str, ...]:
    values = node.get("jobLocation")
    if values is None:
        return ()
    items = values if isinstance(values, list) else [values]
    results: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            value = _string_value(item)
            if value and value not in results:
                results.append(value)
            continue
        address = item.get("address")
        if isinstance(address, dict):
            parts = [
                str(address.get(key) or "").strip()
                for key in ("addressLocality", "addressRegion", "postalCode", "addressCountry")
            ]
            text = ", ".join(part for part in parts if part)
        else:
            text = _string_value(address) or _string_value(item) or ""
        if text and text not in results:
            results.append(text)
    return tuple(results)


def _identifier(node: dict[str, Any], page_url: str) -> str:
    identifier = node.get("identifier")
    if isinstance(identifier, dict):
        identifier = identifier.get("value") or identifier.get("name")
    if identifier:
        return str(identifier).strip()
    canonical = canonicalize_public_url(page_url) or page_url
    return canonical


def _compensation(node: dict[str, Any]) -> tuple[int | None, int | None, str | None, str | None]:
    base = node.get("baseSalary")
    if not isinstance(base, dict):
        return None, None, None, None
    currency = str(base.get("currency") or "").upper() or None
    value = base.get("value")
    if not isinstance(value, dict):
        return None, None, currency, None
    interval = str(value.get("unitText") or "").upper() or None

    def to_int(item: Any) -> int | None:
        if item in {None, ""}:
            return None
        try:
            return int(float(item))
        except (TypeError, ValueError):
            return None

    minimum = to_int(value.get("minValue") or value.get("value"))
    maximum = to_int(value.get("maxValue") or value.get("value"))
    return minimum, maximum, currency, interval


def raw_job_from_jsonld(
    node: dict[str, Any],
    *,
    page_url: str,
    fetched_at: datetime | None = None,
) -> RawJobPosting:
    title = str(node.get("title") or "").strip()
    company_name, company_domain = _organization(node)
    description = html_to_text(str(node.get("description") or ""))
    locations = _locations(node)
    workplace_type = normalize_workplace_type(
        str(node.get("jobLocationType") or ""), locations
    )
    if str(node.get("jobLocationType") or "").casefold() == "telecommute":
        workplace_type = "REMOTE"
    applicant_locations = _string_value(node.get("applicantLocationRequirements"))
    if workplace_type == "REMOTE" and applicant_locations and applicant_locations not in locations:
        locations = (*locations, applicant_locations)
    identifier = _identifier(node, page_url)
    source_url = canonicalize_public_url(str(node.get("url") or page_url)) or page_url
    apply_url = canonicalize_public_url(str(node.get("url") or page_url)) or page_url
    salary_min, salary_max, currency, interval = _compensation(node)
    host = urlsplit(page_url).hostname or "unknown"
    return RawJobPosting(
        source_type=JobSourceType.JSON_LD,
        source_name="json-ld",
        source_company_identity=(company_domain or company_name or host).casefold(),
        source_job_identity=f"{host}:{identifier}",
        external_job_id=f"{host}:{identifier}",
        internal_job_id=identifier,
        source_url=source_url,
        apply_url=apply_url,
        company_name=company_name,
        company_domain=company_domain,
        title=title,
        description=description,
        location_text=locations[0] if locations else None,
        locations=locations,
        employment_type=normalize_employment_type(
            _string_value(node.get("employmentType"))
        ),
        workplace_type=workplace_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        salary_interval=interval,
        salary_provenance="SOURCE_REPORTED" if salary_min is not None or salary_max is not None else None,
        date_posted=_parse_datetime(node.get("datePosted")),
        valid_through=_parse_datetime(node.get("validThrough")),
        fetched_at=fetched_at or datetime.now(timezone.utc),
        raw_payload=node,
        source_metadata={
            "trust_level": SourceTrustLevel.STRUCTURED_JOB_PAGE.value,
            "direct_apply": node.get("directApply"),
            "applicant_location_requirements": applicant_locations,
        },
    )
