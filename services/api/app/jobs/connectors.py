from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


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
        return ConnectorHealth(True, datetime.utcnow(), "Static development connector ready")
