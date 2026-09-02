from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import (
    ConnectorHealth,
    GreenhouseJobBoardConnector,
    JobSourceConnector,
    NormalizedJob,
    html_to_text,
)
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    SourceTrustLevel,
    canonicalize_public_url,
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
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def raw_from_connector(connector: JobSourceConnector, payload: dict[str, Any]) -> RawJobPosting:
    to_raw = getattr(connector, "to_raw", None)
    if callable(to_raw):
        return to_raw(payload)
    normalized = connector.normalize(payload)
    source_url = str(
        payload.get("_applyai_source_url")
        or payload.get("absolute_url")
        or normalized.application_url
    )
    source_type = JobSourceType(connector.key.upper()) if connector.key.upper() in JobSourceType else JobSourceType.DEVELOPMENT_SEED
    source_company_identity = connector.source_company_identity()
    return RawJobPosting(
        source_type=source_type,
        source_name=connector.key,
        source_company_identity=source_company_identity,
        source_job_identity=normalized.external_job_id,
        external_job_id=normalized.external_job_id,
        internal_job_id=(
            str(payload.get("_applyai_internal_job_id"))
            if payload.get("_applyai_internal_job_id") is not None
            else None
        ),
        source_url=source_url,
        apply_url=normalized.application_url,
        company_name=normalized.company_name,
        title=normalized.title,
        description=normalized.description,
        location_text=normalized.locations[0] if normalized.locations else None,
        locations=tuple(normalized.locations),
        employment_type=normalized.employment_type,
        workplace_type=normalized.work_mode,
        seniority=normalized.seniority,
        salary_min=normalized.salary_min,
        salary_max=normalized.salary_max,
        salary_provenance=normalized.salary_provenance,
        date_posted=normalized.posted_at,
        source_updated_at=_parse_datetime(payload.get("_applyai_source_updated_at")),
        fetched_at=_parse_datetime(payload.get("_applyai_fetched_at")),
        raw_payload=payload,
        source_metadata={"trust_level": SourceTrustLevel.OFFICIAL_ATS.value},
        skills=tuple(normalized.skills),
        requirements=tuple(normalized.requirements),
    )


def normalized_from_raw(posting: RawJobPosting) -> NormalizedJob:
    payload = dict(posting.raw_payload)
    payload.update(
        {
            "_applyai_source_type": posting.source_type.value,
            "_applyai_source_name": posting.source_name,
            "_applyai_source_company_identity": posting.source_company_identity,
            "_applyai_source_job_identity": posting.source_job_identity,
            "_applyai_internal_job_id": posting.internal_job_id,
            "_applyai_source_url": posting.source_url,
            "_applyai_canonical_apply_url": canonicalize_public_url(posting.apply_url),
            "_applyai_source_updated_at": (
                posting.source_updated_at.isoformat() if posting.source_updated_at else None
            ),
            "_applyai_fetched_at": (
                posting.fetched_at.isoformat() if posting.fetched_at else None
            ),
            "_applyai_valid_through": (
                posting.valid_through.isoformat() if posting.valid_through else None
            ),
            "_applyai_source_metadata": posting.source_metadata,
        }
    )
    return NormalizedJob(
        external_job_id=posting.external_job_id,
        company_name=posting.company_name,
        title=posting.title,
        description=posting.description,
        application_url=posting.apply_url,
        locations=list(posting.locations),
        work_mode=posting.workplace_type,
        employment_type=posting.employment_type,
        seniority=posting.seniority,
        salary_min=posting.salary_min,
        salary_max=posting.salary_max,
        salary_provenance=posting.salary_provenance,
        skills=list(posting.skills),
        requirements=list(posting.requirements),
        posted_at=posting.date_posted,
        raw_payload=payload,
    )


class LeverJobPostingConnector(JobSourceConnector):
    """Public Lever Postings API adapter for published jobs only."""

    key = "lever"

    def __init__(
        self,
        site: str,
        *,
        company_name: str | None = None,
        region: str = "global",
        client: httpx.Client | None = None,
        timeout_seconds: float = 20.0,
        page_size: int = 100,
        max_pages: int = 20,
    ) -> None:
        site = site.strip()
        if not site or "/" in site or ".." in site:
            raise ValueError("Lever site is invalid")
        if region not in {"global", "eu"}:
            raise ValueError("Lever region must be global or eu")
        self.site = site
        self.company_name = (company_name or site).strip()
        self.region = region
        self.base_url = (
            "https://api.lever.co/v0/postings"
            if region == "global"
            else "https://api.eu.lever.co/v0/postings"
        )
        self.page_size = max(1, min(page_size, 100))
        self.max_pages = max(1, max_pages)
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ApplyAI-JobIngestion/1.0"},
        )
        self._last_fetch_at: datetime | None = None
        self._last_count = 0

    def source_company_identity(self) -> str:
        return self.site

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        del checkpoint
        records: list[dict[str, Any]] = []
        fetched_at = datetime.now(timezone.utc)
        for page in range(self.max_pages):
            skip = page * self.page_size
            response = self.client.get(
                f"{self.base_url}/{self.site}",
                params={"mode": "json", "skip": skip, "limit": self.page_size},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("Lever response did not include a postings list")
            for item in payload:
                if not isinstance(item, dict) or not item.get("id") or not item.get("text"):
                    continue
                records.append(
                    {
                        **item,
                        "_applyai_company_name": self.company_name,
                        "_applyai_lever_site": self.site,
                        "_applyai_source_updated_at": item.get("updatedAt"),
                        "_applyai_fetched_at": fetched_at.isoformat(),
                        "_applyai_company_source_url": f"https://jobs.lever.co/{self.site}",
                        "data_origin": "LEVER_PUBLIC_POSTINGS_API",
                    }
                )
            if len(payload) < self.page_size:
                break
        self._last_fetch_at = fetched_at
        self._last_count = len(records)
        return records

    def to_raw(self, payload: dict[str, Any]) -> RawJobPosting:
        categories = payload.get("categories") if isinstance(payload.get("categories"), dict) else {}
        all_locations = categories.get("allLocations") if isinstance(categories, dict) else None
        locations: list[str] = []
        if isinstance(all_locations, list):
            locations.extend(str(value).strip() for value in all_locations if str(value).strip())
        primary_location = str(categories.get("location") or "").strip() if isinstance(categories, dict) else ""
        if primary_location and primary_location not in locations:
            locations.insert(0, primary_location)

        lists = payload.get("lists") if isinstance(payload.get("lists"), list) else []
        requirements: list[str] = []
        for item in lists:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            content = html_to_text(str(item.get("content") or ""))
            if text and content:
                requirements.append(f"{text}: {content}")
            elif content:
                requirements.append(content)

        description = str(payload.get("descriptionPlain") or "").strip()
        if not description:
            description = html_to_text(str(payload.get("description") or ""))
        salary = payload.get("salaryRange") if isinstance(payload.get("salaryRange"), dict) else {}
        posting_id = str(payload["id"])
        site = str(payload.get("_applyai_lever_site") or self.site)
        workplace_type = normalize_workplace_type(
            str(payload.get("workplaceType") or ""), tuple(locations)
        )
        commitment = str(categories.get("commitment") or "") if isinstance(categories, dict) else ""
        level = str(categories.get("level") or "") if isinstance(categories, dict) else ""
        hosted_url = str(payload.get("hostedUrl") or f"https://jobs.lever.co/{site}/{posting_id}")
        apply_url = str(payload.get("applyUrl") or hosted_url)
        return RawJobPosting(
            source_type=JobSourceType.LEVER,
            source_name="lever",
            source_company_identity=site,
            source_job_identity=f"{site}:{posting_id}",
            external_job_id=f"{site}:{posting_id}",
            internal_job_id=posting_id,
            source_url=hosted_url,
            apply_url=apply_url,
            company_name=str(payload.get("_applyai_company_name") or self.company_name),
            title=str(payload.get("text") or "").strip(),
            description=description,
            location_text=locations[0] if locations else None,
            locations=tuple(locations),
            employment_type=normalize_employment_type(commitment),
            workplace_type=workplace_type,
            seniority=level.upper().replace(" ", "_") if level else "UNKNOWN",
            salary_min=_safe_int(salary.get("min")),
            salary_max=_safe_int(salary.get("max")),
            salary_currency=str(salary.get("currency") or "").upper() or None,
            salary_interval=str(salary.get("interval") or "").upper() or None,
            salary_provenance="SOURCE_REPORTED" if salary else None,
            source_updated_at=_parse_datetime(payload.get("_applyai_source_updated_at")),
            fetched_at=_parse_datetime(payload.get("_applyai_fetched_at")),
            raw_payload=payload,
            source_metadata={
                "trust_level": SourceTrustLevel.OFFICIAL_ATS.value,
                "team": categories.get("team") if isinstance(categories, dict) else None,
                "department": categories.get("department") if isinstance(categories, dict) else None,
                "country": payload.get("country"),
            },
            requirements=tuple(requirements),
        )

    def normalize(self, payload: dict[str, Any]) -> NormalizedJob:
        return normalized_from_raw(self.to_raw(payload))

    def checkpoint(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "region": self.region,
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "count": self._last_count,
        }

    def health(self) -> ConnectorHealth:
        checked_at = datetime.now(timezone.utc)
        try:
            response = self.client.get(
                f"{self.base_url}/{self.site}",
                params={"mode": "json", "limit": 1},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return ConnectorHealth(True, checked_at, "Lever public postings site is reachable")
        except httpx.HTTPError as exc:
            return ConnectorHealth(False, checked_at, f"Lever health check failed: {type(exc).__name__}")


class AshbyJobBoardConnector(JobSourceConnector):
    """Public Ashby job-board API adapter for currently published jobs."""

    key = "ashby"
    base_url = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(
        self,
        board_name: str,
        *,
        company_name: str | None = None,
        include_compensation: bool = True,
        client: httpx.Client | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        board_name = board_name.strip()
        if not board_name or "/" in board_name or ".." in board_name:
            raise ValueError("Ashby board name is invalid")
        self.board_name = board_name
        self.company_name = (company_name or board_name).strip()
        self.include_compensation = include_compensation
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ApplyAI-JobIngestion/1.0"},
        )
        self._last_fetch_at: datetime | None = None
        self._last_count = 0

    def source_company_identity(self) -> str:
        return self.board_name

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        del checkpoint
        response = self.client.get(
            f"{self.base_url}/{self.board_name}",
            params={"includeCompensation": str(self.include_compensation).lower()},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise ValueError("Ashby response did not include a jobs list")
        fetched_at = datetime.now(timezone.utc)
        records: list[dict[str, Any]] = []
        for item in jobs:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            posting_id = item.get("id") or item.get("jobPostingId") or item.get("jobUrl")
            if not posting_id:
                continue
            records.append(
                {
                    **item,
                    "_applyai_ashby_posting_id": str(posting_id),
                    "_applyai_ashby_board_name": self.board_name,
                    "_applyai_company_name": self.company_name,
                    "_applyai_source_updated_at": item.get("updatedAt") or item.get("publishedAt"),
                    "_applyai_fetched_at": fetched_at.isoformat(),
                    "_applyai_company_source_url": f"https://jobs.ashbyhq.com/{self.board_name}",
                    "data_origin": "ASHBY_PUBLIC_JOB_BOARD_API",
                }
            )
        self._last_fetch_at = fetched_at
        self._last_count = len(records)
        return records

    def to_raw(self, payload: dict[str, Any]) -> RawJobPosting:
        posting_id = str(payload.get("_applyai_ashby_posting_id"))
        board_name = str(payload.get("_applyai_ashby_board_name") or self.board_name)
        locations: list[str] = []
        primary = str(payload.get("location") or "").strip()
        if primary:
            locations.append(primary)
        secondary = payload.get("secondaryLocations")
        if isinstance(secondary, list):
            for item in secondary:
                value = str(item.get("location") or "").strip() if isinstance(item, dict) else str(item).strip()
                if value and value not in locations:
                    locations.append(value)
        description = str(payload.get("descriptionPlain") or "").strip()
        if not description:
            description = html_to_text(
                str(payload.get("descriptionHtml") or payload.get("description") or "")
            )
        job_url = str(payload.get("jobUrl") or f"https://jobs.ashbyhq.com/{board_name}/{posting_id}")
        apply_url = str(payload.get("applyUrl") or job_url)
        compensation = payload.get("compensation") if isinstance(payload.get("compensation"), dict) else {}
        employment_type = payload.get("employmentType") or payload.get("employmentTypeLabel")
        workplace_value = payload.get("workplaceType")
        if payload.get("isRemote") is True:
            workplace_value = "remote"
        return RawJobPosting(
            source_type=JobSourceType.ASHBY,
            source_name="ashby",
            source_company_identity=board_name,
            source_job_identity=f"{board_name}:{posting_id}",
            external_job_id=f"{board_name}:{posting_id}",
            internal_job_id=str(payload.get("jobId") or posting_id),
            source_url=job_url,
            apply_url=apply_url,
            company_name=str(payload.get("_applyai_company_name") or self.company_name),
            title=str(payload.get("title") or "").strip(),
            description=description,
            location_text=locations[0] if locations else None,
            locations=tuple(locations),
            employment_type=normalize_employment_type(str(employment_type or "")),
            workplace_type=normalize_workplace_type(str(workplace_value or ""), tuple(locations)),
            salary_min=_safe_int(compensation.get("min") or compensation.get("minimum")),
            salary_max=_safe_int(compensation.get("max") or compensation.get("maximum")),
            salary_currency=str(compensation.get("currency") or "").upper() or None,
            salary_interval=str(compensation.get("interval") or "").upper() or None,
            salary_provenance="SOURCE_REPORTED" if compensation else None,
            date_posted=_parse_datetime(payload.get("publishedAt")),
            source_updated_at=_parse_datetime(payload.get("_applyai_source_updated_at")),
            fetched_at=_parse_datetime(payload.get("_applyai_fetched_at")),
            raw_payload=payload,
            source_metadata={
                "trust_level": SourceTrustLevel.OFFICIAL_ATS.value,
                "department": payload.get("department"),
                "team": payload.get("team"),
                "address": payload.get("address"),
                "secondary_locations": payload.get("secondaryLocations"),
            },
        )

    def normalize(self, payload: dict[str, Any]) -> NormalizedJob:
        return normalized_from_raw(self.to_raw(payload))

    def checkpoint(self) -> dict[str, Any]:
        return {
            "board_name": self.board_name,
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "count": self._last_count,
        }

    def health(self) -> ConnectorHealth:
        checked_at = datetime.now(timezone.utc)
        try:
            response = self.client.get(
                f"{self.base_url}/{self.board_name}",
                params={"includeCompensation": "false"},
            )
            response.raise_for_status()
            return ConnectorHealth(True, checked_at, "Ashby public job board is reachable")
        except httpx.HTTPError as exc:
            return ConnectorHealth(False, checked_at, f"Ashby health check failed: {type(exc).__name__}")


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class JobSourceAdapterFactory:
    @staticmethod
    def create(
        source: JobSourceRegistry,
        *,
        client: httpx.Client | None = None,
    ) -> JobSourceConnector:
        source_type = JobSourceType(source.source_type)
        configuration = dict(source.configuration or {})
        company_name = configuration.get("company_name")
        if source_type == JobSourceType.GREENHOUSE:
            token = str(configuration.get("board_token") or source.source_identity)
            return GreenhouseJobBoardConnector(
                token,
                client=client,
                timeout_seconds=float(configuration.get("timeout_seconds") or 30),
            )
        if source_type == JobSourceType.LEVER:
            site = str(configuration.get("site") or source.source_identity)
            return LeverJobPostingConnector(
                site,
                company_name=str(company_name) if company_name else None,
                region=str(configuration.get("region") or "global"),
                client=client,
                max_pages=int(configuration.get("max_pages") or 20),
            )
        if source_type == JobSourceType.ASHBY:
            board_name = str(configuration.get("board_name") or source.source_identity)
            return AshbyJobBoardConnector(
                board_name,
                company_name=str(company_name) if company_name else None,
                include_compensation=bool(configuration.get("include_compensation", True)),
                client=client,
            )
        raise ValueError(f"No job source adapter is implemented for {source_type.value}")
