from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any

import httpx


@dataclass(frozen=True)
class ConnectorHealth:
    healthy: bool
    checked_at: datetime
    detail: str


@dataclass(frozen=True)
class NormalizedJob:
    external_job_id: str
    company_name: str
    title: str
    description: str
    application_url: str
    locations: list[str]
    work_mode: str
    employment_type: str
    seniority: str
    salary_min: int | None
    salary_max: int | None
    salary_provenance: str | None
    skills: list[str]
    requirements: list[str]
    posted_at: datetime | None
    raw_payload: dict[str, Any]


class JobSourceConnector(ABC):
    key: str

    @abstractmethod
    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, payload: dict[str, Any]) -> NormalizedJob:
        raise NotImplementedError

    @abstractmethod
    def checkpoint(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> ConnectorHealth:
        raise NotImplementedError

    def source_company_identity(self) -> str:
        return self.key


class DevelopmentSeedConnector(JobSourceConnector):
    key = "development-seed"

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        del checkpoint
        return self.records

    def normalize(self, payload: dict[str, Any]) -> NormalizedJob:
        return NormalizedJob(
            external_job_id=str(payload["external_job_id"]),
            company_name=str(payload["company_name"]),
            title=str(payload["title"]),
            description=str(payload["description"]),
            application_url=str(payload["application_url"]),
            locations=[str(item) for item in payload.get("locations", [])],
            work_mode=str(payload.get("work_mode", "ONSITE")).upper(),
            employment_type=str(payload.get("employment_type", "FULL_TIME")).upper(),
            seniority=str(payload.get("seniority", "MID")).upper(),
            salary_min=payload.get("salary_min"),
            salary_max=payload.get("salary_max"),
            salary_provenance=payload.get("salary_provenance"),
            skills=[str(item) for item in payload.get("skills", [])],
            requirements=[str(item) for item in payload.get("requirements", [])],
            posted_at=(
                datetime.fromisoformat(str(payload["posted_at"]))
                if payload.get("posted_at")
                else None
            ),
            raw_payload=payload,
        )

    def checkpoint(self) -> dict[str, Any]:
        return {"count": len(self.records)}

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            True,
            datetime.now(timezone.utc),
            "Static development connector ready",
        )


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def html_to_text(value: str) -> str:
    decoded = unescape(unescape(value))
    parser = _TextExtractor()
    parser.feed(decoded)
    return "\n".join(parser.parts).strip()


class GreenhouseJobBoardConnector(JobSourceConnector):
    """Public Greenhouse Job Board connector using documented public GET endpoints."""

    key = "greenhouse"
    base_url = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(
        self,
        board_token: str,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        token = board_token.strip()
        if not token or "/" in token or ".." in token:
            raise ValueError("Greenhouse board token is invalid")
        self.board_token = token
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ApplyAI-JobIngestion/1.0"},
        )
        self._last_fetch_at: datetime | None = None
        self._last_count = 0
        self._company_name: str | None = None

    def source_company_identity(self) -> str:
        return self.board_token

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        del checkpoint
        board_response = self.client.get(f"{self.base_url}/{self.board_token}")
        board_response.raise_for_status()
        board_payload = board_response.json()
        company_name = str(board_payload.get("name") or self.board_token).strip()
        self._company_name = company_name

        jobs_response = self.client.get(
            f"{self.base_url}/{self.board_token}/jobs",
            params={"content": "true"},
        )
        jobs_response.raise_for_status()
        jobs_payload = jobs_response.json()
        jobs = jobs_payload.get("jobs")
        if not isinstance(jobs, list):
            raise ValueError("Greenhouse response did not include a jobs list")

        fetched_at = datetime.now(timezone.utc)
        records: list[dict[str, Any]] = []
        for item in jobs:
            if not isinstance(item, dict) or item.get("id") is None or not item.get("title"):
                continue
            post_id = str(item["id"])
            internal_job_id = item.get("internal_job_id")
            records.append(
                {
                    **item,
                    "_applyai_company_name": company_name,
                    "_applyai_board_token": self.board_token,
                    "_applyai_greenhouse_post_id": post_id,
                    "_applyai_internal_job_id": (
                        str(internal_job_id) if internal_job_id is not None else None
                    ),
                    "_applyai_source_updated_at": item.get("updated_at"),
                    "_applyai_fetched_at": fetched_at.isoformat(),
                    "_applyai_company_source_url": f"{self.base_url}/{self.board_token}",
                    "data_origin": "GREENHOUSE_PUBLIC_API",
                }
            )
        self._last_fetch_at = fetched_at
        self._last_count = len(records)
        return records

    def normalize(self, payload: dict[str, Any]) -> NormalizedJob:
        location_value = payload.get("location")
        primary_location = ""
        if isinstance(location_value, dict):
            primary_location = str(location_value.get("name") or "").strip()

        locations: list[str] = []
        if primary_location:
            locations.append(primary_location)
        for office in payload.get("offices") or []:
            if not isinstance(office, dict):
                continue
            office_location = str(office.get("location") or "").strip()
            if office_location and office_location not in locations:
                locations.append(office_location)

        location_text = " ".join(locations).lower()
        if "remote" in location_text:
            work_mode = "REMOTE"
        elif "hybrid" in location_text:
            work_mode = "HYBRID"
        else:
            work_mode = "UNKNOWN"

        description = html_to_text(str(payload.get("content") or ""))
        if not description:
            description = "Description not provided by source."

        post_id = str(payload["id"])
        board_token = str(payload.get("_applyai_board_token") or self.board_token)
        return NormalizedJob(
            # Greenhouse post ids are only source identities within a board. The board
            # token is therefore part of the deterministic source identity.
            external_job_id=f"{board_token}:{post_id}",
            company_name=str(payload.get("_applyai_company_name") or self.board_token),
            title=str(payload["title"]).strip(),
            description=description,
            application_url=str(payload.get("absolute_url") or "").strip(),
            locations=locations,
            work_mode=work_mode,
            employment_type="UNKNOWN",
            seniority="UNKNOWN",
            salary_min=None,
            salary_max=None,
            salary_provenance=None,
            skills=[],
            requirements=[],
            posted_at=None,
            raw_payload=payload,
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "board_token": self.board_token,
            "company_name": self._company_name,
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "count": self._last_count,
        }

    def health(self) -> ConnectorHealth:
        checked_at = datetime.now(timezone.utc)
        try:
            response = self.client.get(f"{self.base_url}/{self.board_token}")
            response.raise_for_status()
            return ConnectorHealth(True, checked_at, "Greenhouse public board is reachable")
        except httpx.HTTPError as exc:
            return ConnectorHealth(
                False,
                checked_at,
                f"Greenhouse health check failed: {type(exc).__name__}",
            )
