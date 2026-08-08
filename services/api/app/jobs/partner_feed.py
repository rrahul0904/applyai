from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree

from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    SourceTrustLevel,
    normalize_employment_type,
    normalize_workplace_type,
)
from app.jobs.web_security import CrawlBudget, SafeHttpFetcher


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").replace("$", "").strip()))
    except (TypeError, ValueError):
        return None


def _field(payload: dict[str, Any], path: str | None) -> Any:
    if not path:
        return None
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_item(element: ElementTree.Element) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for child in element.iter():
        if child is element:
            continue
        name = _local_name(child.tag)
        text = " ".join((child.text or "").split()).strip()
        if not text:
            continue
        if name in item:
            existing = item[name]
            item[name] = [*existing, text] if isinstance(existing, list) else [existing, text]
        else:
            item[name] = text
    return item


DEFAULT_FIELD_MAP = {
    "id": "id",
    "title": "title",
    "company": "company",
    "description": "description",
    "apply_url": "apply_url",
    "source_url": "url",
    "location": "location",
    "employment_type": "employment_type",
    "workplace_type": "workplace_type",
    "posted_at": "date_posted",
    "valid_through": "valid_through",
    "salary_min": "salary_min",
    "salary_max": "salary_max",
    "salary_currency": "salary_currency",
    "salary_interval": "salary_interval",
    "requisition_id": "requisition_id",
}


class PartnerFeedConnector(JobSourceConnector):
    """Contracted/licensed feed connector for JSON, JSONL, CSV and XML/RSS/Atom.

    This connector intentionally requires an explicitly registered feed URL and field map.
    It is not a marketplace crawler. Authentication-heavy partner APIs should use dedicated
    connectors or pre-signed/private delivery transformed into an approved public/signed URL.
    """

    key = "authorized_feed"

    def __init__(
        self,
        *,
        feed_url: str,
        source_identity: str,
        provider_key: str,
        feed_format: str = "json",
        field_map: dict[str, str] | None = None,
        source_type: JobSourceType = JobSourceType.AUTHORIZED_AGGREGATOR_FEED,
        trust_level: SourceTrustLevel = SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED,
        authoritative_snapshot: bool = False,
        max_response_bytes: int = 20 * 1024 * 1024,
        timeout_seconds: float = 30.0,
        fetcher: SafeHttpFetcher | None = None,
    ) -> None:
        self.feed_url = feed_url.strip()
        self.identity = source_identity.strip()
        self.provider_key = provider_key.strip().casefold()
        self.feed_format = feed_format.casefold().lstrip(".")
        if self.feed_format not in {"json", "jsonl", "csv", "xml", "rss", "atom"}:
            raise ValueError("Partner feed format must be json, jsonl, csv, xml, rss or atom")
        if not self.feed_url or not self.identity or not self.provider_key:
            raise ValueError("Partner feed URL, source identity and provider key are required")
        self.field_map = {**DEFAULT_FIELD_MAP, **dict(field_map or {})}
        self.source_type = source_type
        self.trust_level = trust_level
        self._authoritative_snapshot = bool(authoritative_snapshot)
        self._owns_fetcher = fetcher is None
        self.fetcher = fetcher or SafeHttpFetcher(
            budget=CrawlBudget(
                max_pages=1,
                max_response_bytes=max_response_bytes,
                max_redirects=4,
                request_timeout_seconds=timeout_seconds,
            ),
            user_agent="ApplyAI-PartnerFeed/1.0",
        )
        self._last_fetch_at: datetime | None = None
        self._last_count = 0
        self._last_final_url: str | None = None
        self._last_etag: str | None = None
        self._last_modified: str | None = None

    @property
    def authoritative_snapshot(self) -> bool:
        return self._authoritative_snapshot

    def source_company_identity(self) -> str:
        return self.identity

    def close(self) -> None:
        if self._owns_fetcher:
            self.fetcher.close()

    def _parse(self, content: bytes) -> list[dict[str, Any]]:
        if self.feed_format == "json":
            payload = json.loads(content.decode("utf-8-sig"))
            if isinstance(payload, list):
                return [dict(item) for item in payload if isinstance(item, dict)]
            if isinstance(payload, dict):
                for key in ("jobs", "data", "results", "items", "postings"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return [dict(item) for item in value if isinstance(item, dict)]
            raise ValueError("Partner JSON feed must contain a job list")
        if self.feed_format == "jsonl":
            return [
                dict(json.loads(line))
                for line in content.decode("utf-8-sig").splitlines()
                if line.strip()
            ]
        if self.feed_format == "csv":
            return [
                dict(row)
                for row in csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
            ]
        root = ElementTree.fromstring(content)
        entries = [
            element
            for element in root.iter()
            if _local_name(element.tag).casefold() in {"item", "entry", "job", "posting"}
        ]
        if not entries:
            entries = list(root)
        return [_xml_item(element) for element in entries]

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        checkpoint = checkpoint or {}
        result = self.fetcher.fetch(
            self.feed_url,
            accept="application/json,application/x-ndjson,text/csv,application/xml,text/xml,application/rss+xml,application/atom+xml;q=0.9",
            etag=checkpoint.get("etag"),
            last_modified=checkpoint.get("last_modified"),
        )
        if result.status_code == 304:
            self._last_fetch_at = datetime.now(timezone.utc)
            self._last_count = 0
            return []
        if result.status_code >= 400:
            raise ValueError(f"Partner feed returned HTTP {result.status_code}")
        records = self._parse(result.content)
        fetched_at = datetime.now(timezone.utc)
        normalized = [
            {
                **record,
                "_applyai_fetched_at": fetched_at.isoformat(),
                "_applyai_feed_item_index": index,
            }
            for index, record in enumerate(records)
        ]
        self._last_fetch_at = fetched_at
        self._last_count = len(normalized)
        self._last_final_url = result.final_url
        self._last_etag = result.etag
        self._last_modified = result.last_modified
        return normalized

    def to_raw(self, payload: dict[str, Any]) -> RawJobPosting:
        identifier = str(_field(payload, self.field_map["id"]) or "").strip()
        if not identifier:
            identifier = str(payload.get("_applyai_feed_item_index") or "").strip()
        title = str(_field(payload, self.field_map["title"]) or "").strip()
        company = str(_field(payload, self.field_map["company"]) or self.identity).strip()
        description = str(_field(payload, self.field_map["description"]) or "").strip()
        source_url = str(
            _field(payload, self.field_map["source_url"])
            or _field(payload, self.field_map["apply_url"])
            or self.feed_url
        ).strip()
        apply_url = str(_field(payload, self.field_map["apply_url"]) or source_url).strip()
        location_value = _field(payload, self.field_map["location"])
        if isinstance(location_value, list):
            locations = tuple(str(value).strip() for value in location_value if str(value).strip())
        else:
            location_text = str(location_value or "").strip()
            locations = (location_text,) if location_text else ()
        requisition = str(_field(payload, self.field_map["requisition_id"]) or identifier).strip()
        return RawJobPosting(
            source_type=self.source_type,
            source_name=self.provider_key,
            source_company_identity=self.identity,
            source_job_identity=f"{self.provider_key}:{identifier}",
            external_job_id=f"{self.provider_key}:{self.identity}:{identifier}",
            internal_job_id=requisition or None,
            company_name=company,
            title=title,
            description=description,
            source_url=source_url,
            apply_url=apply_url,
            location_text=locations[0] if locations else None,
            locations=locations,
            employment_type=normalize_employment_type(
                str(_field(payload, self.field_map["employment_type"]) or "")
            ),
            workplace_type=normalize_workplace_type(
                str(_field(payload, self.field_map["workplace_type"]) or ""), locations
            ),
            salary_min=_to_int(_field(payload, self.field_map["salary_min"])),
            salary_max=_to_int(_field(payload, self.field_map["salary_max"])),
            salary_currency=str(_field(payload, self.field_map["salary_currency"]) or "").strip() or None,
            salary_interval=str(_field(payload, self.field_map["salary_interval"]) or "").strip() or None,
            salary_provenance="SOURCE_REPORTED",
            date_posted=_parse_datetime(_field(payload, self.field_map["posted_at"])),
            valid_through=_parse_datetime(_field(payload, self.field_map["valid_through"])),
            fetched_at=_parse_datetime(payload.get("_applyai_fetched_at")),
            raw_payload=payload,
            source_metadata={
                "provider_key": self.provider_key,
                "trust_level": self.trust_level.value,
                "feed_format": self.feed_format,
                "authorized_feed": True,
            },
        )

    def normalize(self, payload: dict[str, Any]) -> NormalizedJob:
        raw = self.to_raw(payload)
        return NormalizedJob(
            external_job_id=raw.external_job_id,
            company_name=raw.company_name,
            title=raw.title,
            description=raw.description,
            application_url=raw.apply_url,
            locations=list(raw.locations),
            work_mode=raw.workplace_type,
            employment_type=raw.employment_type,
            seniority=raw.seniority,
            salary_min=raw.salary_min,
            salary_max=raw.salary_max,
            salary_provenance=raw.salary_provenance,
            skills=list(raw.skills),
            requirements=list(raw.requirements),
            posted_at=raw.date_posted,
            raw_payload={
                **payload,
                "_applyai_internal_job_id": raw.internal_job_id,
                "_applyai_source_url": raw.source_url,
                "_applyai_source_metadata": raw.source_metadata,
                "data_origin": "AUTHORIZED_LICENSED_FEED",
            },
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "count": self._last_count,
            "final_url": self._last_final_url,
            "etag": self._last_etag,
            "last_modified": self._last_modified,
            "authoritative_snapshot": self._authoritative_snapshot,
        }

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            True,
            datetime.now(timezone.utc),
            "Authorized/licensed feed configuration is structurally valid; live reachability is checked during fetch.",
        )
