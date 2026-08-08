from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob, html_to_text
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    SourceTrustLevel,
    normalize_employment_type,
    normalize_workplace_type,
)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


class USAJobsConnector(JobSourceConnector):
    """Official USAJOBS Search API connector for currently open federal jobs."""

    key = "usajobs"
    endpoint = "https://data.usajobs.gov/api/search"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        user_agent: str | None = None,
        results_per_page: int = 500,
        max_pages: int = 20,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = (api_key or os.getenv("USAJOBS_API_KEY") or "").strip()
        self.user_agent = (user_agent or os.getenv("USAJOBS_USER_AGENT") or "").strip()
        if not self.api_key:
            raise ValueError("USAJOBS_API_KEY is required")
        if not self.user_agent:
            raise ValueError("USAJOBS_USER_AGENT is required")
        self.results_per_page = max(1, min(int(results_per_page), 500))
        self.max_pages = max(1, int(max_pages))
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        self._last_fetch_at: datetime | None = None
        self._last_count = 0

    def source_company_identity(self) -> str:
        return "us-federal-government"

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Host": "data.usajobs.gov",
            "User-Agent": self.user_agent,
            "Authorization-Key": self.api_key,
            "Accept": "application/json",
        }

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        del checkpoint
        fetched_at = datetime.now(timezone.utc)
        records: list[dict[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            response = self.client.get(
                self.endpoint,
                params={"Page": page, "ResultsPerPage": self.results_per_page, "Fields": "Full"},
                headers=self._headers(),
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("SearchResult") if isinstance(payload, dict) else None
            items = result.get("SearchResultItems") if isinstance(result, dict) else None
            if not isinstance(items, list):
                raise ValueError("USAJOBS response did not include SearchResultItems")
            for item in items:
                if not isinstance(item, dict):
                    continue
                descriptor = item.get("MatchedObjectDescriptor")
                if not isinstance(descriptor, dict) or not descriptor.get("PositionTitle"):
                    continue
                records.append({**item, "_applyai_fetched_at": fetched_at.isoformat()})
            total = _to_int(result.get("SearchResultCountAll")) if isinstance(result, dict) else None
            if not items or len(items) < self.results_per_page or (total is not None and len(records) >= total):
                break
        self._last_fetch_at = fetched_at
        self._last_count = len(records)
        return records

    def to_raw(self, payload: dict[str, Any]) -> RawJobPosting:
        descriptor = payload.get("MatchedObjectDescriptor") or {}
        user_area = descriptor.get("UserArea") if isinstance(descriptor.get("UserArea"), dict) else {}
        details = user_area.get("Details") if isinstance(user_area.get("Details"), dict) else {}
        positions = descriptor.get("PositionLocation") if isinstance(descriptor.get("PositionLocation"), list) else []
        locations = tuple(
            str(item.get("LocationName") or "").strip()
            for item in positions
            if isinstance(item, dict) and str(item.get("LocationName") or "").strip()
        )
        remuneration = descriptor.get("PositionRemuneration")
        remuneration = remuneration[0] if isinstance(remuneration, list) and remuneration else {}
        apply_uri = descriptor.get("ApplyURI")
        if isinstance(apply_uri, list):
            apply_url = str(apply_uri[0]) if apply_uri else ""
        else:
            apply_url = str(apply_uri or descriptor.get("PositionURI") or "")
        position_id = str(descriptor.get("PositionID") or payload.get("MatchedObjectId") or "")
        organization = str(descriptor.get("OrganizationName") or descriptor.get("DepartmentName") or "US Federal Government")
        summary_parts = [
            str(descriptor.get("QualificationSummary") or ""),
            str(details.get("JobSummary") or ""),
            str(details.get("MajorDuties") or ""),
            str(details.get("Requirements") or ""),
        ]
        description = "\n\n".join(part.strip() for part in summary_parts if part and part.strip())
        if len(description) < 40:
            description = f"Federal job opportunity with {organization}. See the official USAJOBS announcement for full duties and qualifications."
        schedule = str(descriptor.get("PositionSchedule") or "")
        offering = str(descriptor.get("PositionOfferingType") or "")
        remote = bool(details.get("RemoteIndicator"))
        workplace = "REMOTE" if remote else normalize_workplace_type(None, locations)
        source_url = str(descriptor.get("PositionURI") or apply_url)
        posted = _parse_datetime(descriptor.get("PublicationStartDate"))
        valid_through = _parse_datetime(descriptor.get("ApplicationCloseDate"))
        return RawJobPosting(
            source_type=JobSourceType.USAJOBS,
            source_name="usajobs",
            source_company_identity="us-federal-government",
            source_job_identity=position_id,
            external_job_id=f"usajobs:{position_id}",
            internal_job_id=position_id,
            source_url=source_url,
            apply_url=apply_url or source_url,
            company_name=organization,
            title=str(descriptor.get("PositionTitle") or "").strip(),
            description=description,
            location_text=locations[0] if locations else None,
            locations=locations,
            employment_type=normalize_employment_type(schedule or offering),
            workplace_type=workplace,
            salary_min=_to_int(remuneration.get("MinimumRange")) if isinstance(remuneration, dict) else None,
            salary_max=_to_int(remuneration.get("MaximumRange")) if isinstance(remuneration, dict) else None,
            salary_currency="USD",
            salary_interval="YEAR",
            salary_provenance="SOURCE_REPORTED",
            date_posted=posted,
            valid_through=valid_through,
            fetched_at=_parse_datetime(payload.get("_applyai_fetched_at")),
            raw_payload=payload,
            source_metadata={
                "trust_level": SourceTrustLevel.GOVERNMENT_OFFICIAL.value,
                "department": descriptor.get("DepartmentName"),
                "agency": descriptor.get("OrganizationName"),
                "job_category": descriptor.get("JobCategory"),
                "security_clearance": details.get("SecurityClearance"),
                "who_may_apply": details.get("WhoMayApply"),
                "hiring_path": details.get("HiringPath"),
                "remote_indicator": details.get("RemoteIndicator"),
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
                "_applyai_fetched_at": raw.fetched_at.isoformat() if raw.fetched_at else None,
                "_applyai_source_metadata": raw.source_metadata,
                "data_origin": "USAJOBS_OFFICIAL_API",
            },
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "count": self._last_count,
        }

    def health(self) -> ConnectorHealth:
        checked_at = datetime.now(timezone.utc)
        try:
            response = self.client.get(
                self.endpoint,
                params={"ResultsPerPage": 1},
                headers=self._headers(),
            )
            response.raise_for_status()
            return ConnectorHealth(True, checked_at, "USAJOBS Search API is reachable")
        except httpx.HTTPError as exc:
            return ConnectorHealth(False, checked_at, f"USAJOBS health check failed: {type(exc).__name__}")


class ReliefWebJobsConnector(JobSourceConnector):
    """Official ReliefWeb v2 jobs API connector for humanitarian opportunities."""

    key = "reliefweb"
    endpoint = "https://api.reliefweb.int/v2/jobs"

    def __init__(
        self,
        *,
        appname: str | None = None,
        page_size: int = 1000,
        max_pages: int = 20,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.appname = (appname or os.getenv("RELIEFWEB_APPNAME") or "").strip()
        if not self.appname:
            raise ValueError("RELIEFWEB_APPNAME is required")
        self.page_size = max(1, min(int(page_size), 1000))
        self.max_pages = max(1, int(max_pages))
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        self._last_fetch_at: datetime | None = None
        self._last_count = 0

    def source_company_identity(self) -> str:
        return "reliefweb"

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        del checkpoint
        records: list[dict[str, Any]] = []
        fetched_at = datetime.now(timezone.utc)
        for page in range(self.max_pages):
            offset = page * self.page_size
            response = self.client.get(
                self.endpoint,
                params={
                    "appname": self.appname,
                    "limit": self.page_size,
                    "offset": offset,
                    "profile": "full",
                    "sort[]": "date.created:desc",
                },
                headers={"Accept": "application/json", "User-Agent": "ApplyAI-JobIngestion/1.0"},
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list):
                raise ValueError("ReliefWeb response did not include a data list")
            for item in data:
                if isinstance(item, dict) and item.get("id"):
                    records.append({**item, "_applyai_fetched_at": fetched_at.isoformat()})
            total = _to_int(payload.get("totalCount")) if isinstance(payload, dict) else None
            if not data or len(data) < self.page_size or (total is not None and len(records) >= total):
                break
        self._last_fetch_at = fetched_at
        self._last_count = len(records)
        return records

    def to_raw(self, payload: dict[str, Any]) -> RawJobPosting:
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
        identifier = str(payload.get("id") or fields.get("id") or "")
        sources = fields.get("source") if isinstance(fields.get("source"), list) else []
        source_name = "ReliefWeb humanitarian employer"
        if sources and isinstance(sources[0], dict):
            source_name = str(sources[0].get("name") or source_name)
        countries = fields.get("country") if isinstance(fields.get("country"), list) else []
        locations = tuple(
            str(item.get("name") or "").strip()
            for item in countries
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        )
        body = fields.get("body")
        if isinstance(body, str):
            description = html_to_text(body)
        else:
            description = str(fields.get("description") or "").strip()
        how_to_apply = fields.get("how_to_apply")
        if isinstance(how_to_apply, str) and len(description) < 40:
            description = html_to_text(how_to_apply)
        url = str(fields.get("url") or f"https://reliefweb.int/job/{identifier}")
        apply_url = str(fields.get("url_alias") or fields.get("url") or url)
        job_types = fields.get("job_type") if isinstance(fields.get("job_type"), list) else []
        job_type = str(job_types[0].get("name") or "") if job_types and isinstance(job_types[0], dict) else ""
        return RawJobPosting(
            source_type=JobSourceType.RELIEFWEB,
            source_name="reliefweb",
            source_company_identity="reliefweb",
            source_job_identity=identifier,
            external_job_id=f"reliefweb:{identifier}",
            internal_job_id=identifier,
            source_url=url,
            apply_url=apply_url,
            company_name=source_name,
            title=str(fields.get("title") or "").strip(),
            description=description,
            location_text=locations[0] if locations else None,
            locations=locations,
            employment_type=normalize_employment_type(job_type),
            workplace_type=normalize_workplace_type(None, locations),
            date_posted=_parse_datetime(fields.get("date", {}).get("created") if isinstance(fields.get("date"), dict) else None),
            valid_through=_parse_datetime(fields.get("date", {}).get("closing") if isinstance(fields.get("date"), dict) else fields.get("closing_date")),
            fetched_at=_parse_datetime(payload.get("_applyai_fetched_at")),
            raw_payload=payload,
            source_metadata={
                "trust_level": SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED.value,
                "career_categories": fields.get("career_categories") or fields.get("career_category"),
                "experience": fields.get("experience") or fields.get("job_experience"),
                "theme": fields.get("theme"),
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
                "_applyai_fetched_at": raw.fetched_at.isoformat() if raw.fetched_at else None,
                "_applyai_source_metadata": raw.source_metadata,
                "data_origin": "RELIEFWEB_OFFICIAL_API",
            },
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "count": self._last_count,
        }

    def health(self) -> ConnectorHealth:
        checked_at = datetime.now(timezone.utc)
        try:
            response = self.client.get(
                self.endpoint,
                params={"appname": self.appname, "limit": 1},
                headers={"Accept": "application/json", "User-Agent": "ApplyAI-JobIngestion/1.0"},
            )
            response.raise_for_status()
            return ConnectorHealth(True, checked_at, "ReliefWeb jobs API is reachable")
        except httpx.HTTPError as exc:
            return ConnectorHealth(False, checked_at, f"ReliefWeb health check failed: {type(exc).__name__}")
