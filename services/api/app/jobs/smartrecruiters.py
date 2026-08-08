from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob, html_to_text
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    SourceTrustLevel,
    normalize_employment_type,
)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class SmartRecruitersPostingConnector(JobSourceConnector):
    """SmartRecruiters public Posting API connector for an employer company identifier."""

    key = "smartrecruiters"
    api_root = "https://api.smartrecruiters.com/v1/companies"

    def __init__(
        self,
        company_identifier: str,
        *,
        page_size: int = 100,
        max_pages: int = 20,
        max_jobs: int = 2000,
        request_interval_seconds: float = 0.11,
        client: httpx.Client | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        identifier = company_identifier.strip()
        if not identifier or "/" in identifier or ".." in identifier:
            raise ValueError("SmartRecruiters company identifier is invalid")
        self.company_identifier = identifier
        self.page_size = max(1, min(int(page_size), 100))
        self.max_pages = max(1, int(max_pages))
        self.max_jobs = max(1, int(max_jobs))
        self.request_interval_seconds = max(0.0, float(request_interval_seconds))
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ApplyAI-JobIngestion/1.0", "Accept": "application/json"},
        )
        self._last_request_at = 0.0
        self._last_fetch_at: datetime | None = None
        self._last_count = 0
        self._authoritative_snapshot = False

    @property
    def authoritative_snapshot(self) -> bool:
        return self._authoritative_snapshot

    def source_company_identity(self) -> str:
        return self.company_identifier

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _get(self, url: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        elapsed = time.monotonic() - self._last_request_at
        if self.request_interval_seconds and elapsed < self.request_interval_seconds:
            time.sleep(self.request_interval_seconds - elapsed)
        response = self.client.get(url, params=params)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        del checkpoint
        base = f"{self.api_root}/{self.company_identifier}/postings"
        summaries: list[dict[str, Any]] = []
        total_found: int | None = None
        exhausted = False
        for page in range(self.max_pages):
            offset = page * self.page_size
            payload = self._get(
                base,
                params={"offset": offset, "limit": self.page_size, "destination": "PUBLIC"},
            ).json()
            content = payload.get("content") if isinstance(payload, dict) else None
            if not isinstance(content, list):
                raise ValueError("SmartRecruiters response did not include a posting content list")
            if total_found is None:
                try:
                    total_found = int(payload.get("totalFound"))
                except (TypeError, ValueError):
                    total_found = None
            summaries.extend(item for item in content if isinstance(item, dict))
            if not content or len(content) < self.page_size or (
                total_found is not None and len(summaries) >= total_found
            ):
                exhausted = True
                break
            if len(summaries) >= self.max_jobs:
                break

        summaries = summaries[: self.max_jobs]
        details: list[dict[str, Any]] = []
        fetched_at = datetime.now(timezone.utc)
        for summary in summaries:
            posting_id = summary.get("uuid") or summary.get("id")
            if not posting_id:
                continue
            detail = self._get(f"{base}/{posting_id}").json()
            if not isinstance(detail, dict):
                raise ValueError("SmartRecruiters posting detail was not an object")
            details.append(
                {
                    **detail,
                    "_applyai_fetched_at": fetched_at.isoformat(),
                    "_applyai_company_identifier": self.company_identifier,
                    "data_origin": "SMARTRECRUITERS_PUBLIC_POSTING_API",
                }
            )

        self._authoritative_snapshot = exhausted and (
            total_found is None or len(summaries) >= total_found
        ) and len(summaries) <= self.max_jobs
        self._last_fetch_at = fetched_at
        self._last_count = len(details)
        return details

    def to_raw(self, payload: dict[str, Any]) -> RawJobPosting:
        posting_id = str(payload.get("uuid") or payload.get("id") or "")
        company = payload.get("company") if isinstance(payload.get("company"), dict) else {}
        location = payload.get("location") if isinstance(payload.get("location"), dict) else {}
        parts = [
            str(location.get("city") or "").strip(),
            str(location.get("region") or "").strip(),
            str(location.get("country") or "").strip().upper(),
        ]
        location_text = ", ".join(part for part in parts if part)
        job_ad = payload.get("jobAd") if isinstance(payload.get("jobAd"), dict) else {}
        sections = job_ad.get("sections") if isinstance(job_ad.get("sections"), dict) else {}
        description_parts: list[str] = []
        requirements: list[str] = []
        for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
            section = sections.get(key) if isinstance(sections.get(key), dict) else {}
            text = html_to_text(str(section.get("text") or ""))
            if text:
                description_parts.append(text)
                if key == "qualifications":
                    requirements.append(text)
        description = "\n\n".join(description_parts)
        apply_url = str(payload.get("applyUrl") or "").strip()
        if not apply_url:
            apply_url = f"https://jobs.smartrecruiters.com/{self.company_identifier}/{posting_id}"
        employment = payload.get("typeOfEmployment")
        employment_label = (
            str(employment.get("label") or "") if isinstance(employment, dict) else str(employment or "")
        )
        experience = payload.get("experienceLevel")
        seniority = (
            str(experience.get("label") or "UNKNOWN").upper().replace(" ", "_").replace("-", "_")
            if isinstance(experience, dict)
            else "UNKNOWN"
        )
        remote = bool(location.get("remote"))
        company_name = str(company.get("name") or self.company_identifier)
        source_url = f"https://jobs.smartrecruiters.com/{self.company_identifier}/{posting_id}"
        return RawJobPosting(
            source_type=JobSourceType.SMARTRECRUITERS,
            source_name="smartrecruiters",
            source_company_identity=self.company_identifier,
            source_job_identity=f"{self.company_identifier}:{posting_id}",
            external_job_id=f"{self.company_identifier}:{posting_id}",
            internal_job_id=str(payload.get("jobId") or posting_id),
            source_url=source_url,
            apply_url=apply_url,
            company_name=company_name,
            title=str(payload.get("name") or "").strip(),
            description=description,
            location_text=location_text or None,
            locations=(location_text,) if location_text else (),
            employment_type=normalize_employment_type(employment_label),
            workplace_type="REMOTE" if remote else "UNKNOWN",
            seniority=seniority,
            date_posted=_parse_datetime(payload.get("releasedDate")),
            fetched_at=_parse_datetime(payload.get("_applyai_fetched_at")),
            raw_payload=payload,
            source_metadata={
                "trust_level": SourceTrustLevel.OFFICIAL_ATS.value,
                "industry": payload.get("industry"),
                "department": payload.get("department"),
                "function": payload.get("function"),
            },
            requirements=tuple(requirements),
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
            raw_payload=payload,
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "company_identifier": self.company_identifier,
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "count": self._last_count,
            "authoritative_snapshot": self._authoritative_snapshot,
        }

    def health(self) -> ConnectorHealth:
        checked_at = datetime.now(timezone.utc)
        try:
            self._get(
                f"{self.api_root}/{self.company_identifier}/postings",
                params={"offset": 0, "limit": 1, "destination": "PUBLIC"},
            )
            return ConnectorHealth(True, checked_at, "SmartRecruiters public Posting API is reachable")
        except httpx.HTTPError as exc:
            return ConnectorHealth(
                False,
                checked_at,
                f"SmartRecruiters health check failed: {type(exc).__name__}",
            )
