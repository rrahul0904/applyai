from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

import httpx

from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    SourceTrustLevel,
    normalize_employment_type,
    normalize_workplace_type,
)


DEFAULT_OPEN_JOBS_DATA_BASE_URL = "https://backend.dehnbostele.workers.dev/data"


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromtimestamp(float(text) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class OpenJobsConnector(JobSourceConnector):
    """Bounded connector for the public CC0 Open Jobs corpus.

    Open Jobs publishes a local-first tree manifest and leaf-group JSON files. ApplyAI
    intentionally consumes those small public group files instead of loading the multi-GB
    Parquet snapshot into API memory. Each source run advances through a bounded number of
    leaves and persists a checkpoint through the normal source registry.

    This source is discovery/coverage evidence, not closure authority. Employer-origin ATS
    observations remain higher-authority canonical sources when the same role is observed.
    """

    key = "open-jobs"
    authoritative_snapshot = False
    source_completeness = "PARTIAL"

    def __init__(
        self,
        *,
        data_base_url: str = DEFAULT_OPEN_JOBS_DATA_BASE_URL,
        max_groups_per_run: int = 40,
        max_jobs_per_group: int = 1000,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        base = data_base_url.strip().rstrip("/")
        if not base.startswith("https://"):
            raise ValueError("Open Jobs data base URL must use HTTPS")
        self.data_base_url = base
        self.max_groups_per_run = max(1, min(int(max_groups_per_run), 250))
        self.max_jobs_per_group = max(1, min(int(max_jobs_per_group), 2000))
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "ApplyAI-OpenJobs-Ingestion/1.0",
                "Accept": "application/json",
            },
        )
        self._last_leaf_id: str | None = None
        self._last_fetch_at: datetime | None = None
        self._manifest_recipe: str | None = None
        self._manifest_jobs: int | None = None
        self._manifest_leaves: int | None = None
        self._groups_processed = 0
        self._jobs_seen = 0
        self._cycle_complete = False

    def source_company_identity(self) -> str:
        return "open-jobs"

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _manifest(self) -> dict[str, Any]:
        response = self.client.get(f"{self.data_base_url}/manifest.json")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("tree"), list):
            raise ValueError("Open Jobs manifest did not contain a tree")
        return payload

    @staticmethod
    def _leaf_ids(manifest: dict[str, Any]) -> list[str]:
        leaves: list[str] = []
        for node in manifest.get("tree", []):
            if not isinstance(node, dict):
                continue
            children = node.get("children")
            if children not in (None, []) and isinstance(children, list) and children:
                continue
            node_id = node.get("id")
            if node_id is not None:
                leaves.append(str(node_id))
        return leaves

    def iter_batches(
        self,
        checkpoint: dict[str, Any] | None,
    ) -> Iterator[list[dict[str, Any]]]:
        manifest = self._manifest()
        leaves = self._leaf_ids(manifest)
        if not leaves:
            raise ValueError("Open Jobs manifest has no leaf groups")

        self._manifest_recipe = str(manifest.get("recipe") or "") or None
        self._manifest_jobs = int(manifest.get("jobs") or 0) or None
        self._manifest_leaves = int(manifest.get("leaves") or len(leaves))
        previous_leaf = str((checkpoint or {}).get("last_leaf_id") or "")
        start = 0
        if previous_leaf:
            try:
                start = leaves.index(previous_leaf) + 1
            except ValueError:
                # Group ids can change when the upstream corpus is rebuilt. Restarting is
                # idempotent because ApplyAI canonicalization keys observations by source id.
                start = 0
        if start >= len(leaves):
            start = 0

        selected = leaves[start : start + self.max_groups_per_run]
        self._cycle_complete = start + len(selected) >= len(leaves)
        fetched_at = datetime.now(timezone.utc)
        self._last_fetch_at = fetched_at
        self._groups_processed = 0
        self._jobs_seen = 0

        for leaf_id in selected:
            response = self.client.get(f"{self.data_base_url}/groups/{leaf_id}.json")
            response.raise_for_status()
            group = response.json()
            jobs = group.get("jobs") if isinstance(group, dict) else None
            if not isinstance(jobs, list):
                raise ValueError(f"Open Jobs group {leaf_id} did not contain jobs")

            records: list[dict[str, Any]] = []
            for item in jobs[: self.max_jobs_per_group]:
                if not isinstance(item, dict):
                    continue
                job_id = item.get("id")
                title = str(item.get("title") or "").strip()
                url = str(item.get("url") or "").strip()
                if job_id is None or not title or not url:
                    continue
                # Do not persist the 1536-d embedding blob from each group. ApplyAI owns its
                # own semantic index and only needs the public job observation/evidence here.
                record = {key: value for key, value in item.items() if key != "v"}
                record.update(
                    {
                        "_applyai_open_jobs_leaf_id": leaf_id,
                        "_applyai_fetched_at": fetched_at.isoformat(),
                        "_applyai_source_url": f"{self.data_base_url}/groups/{leaf_id}.json",
                        "data_origin": "OPEN_JOBS_CC0",
                    }
                )
                records.append(record)

            self._last_leaf_id = leaf_id
            self._groups_processed += 1
            self._jobs_seen += len(records)
            yield records

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        # Compatibility path for callers that have not adopted iter_batches. The configured
        # group bound keeps this finite, but production registry ingestion consumes batches.
        return [record for batch in self.iter_batches(checkpoint) for record in batch]

    def to_raw(self, payload: dict[str, Any]) -> RawJobPosting:
        ats = str(payload.get("ats") or "unknown").strip().casefold()
        slug = str(payload.get("slug") or "unknown").strip()
        upstream_id = str(payload.get("id"))
        company_name = str(payload.get("company") or slug or ats).strip()
        external_id = f"{ats}:{slug}:{upstream_id}"
        location = str(payload.get("location") or "").strip()
        description = str(payload.get("jd") or payload.get("jd_markdown") or "").strip()
        apply_url = str(payload.get("url") or "").strip()
        seen_at = _parse_datetime(payload.get("seen"))
        fetched_at = _parse_datetime(payload.get("_applyai_fetched_at"))
        leaf_id = str(payload.get("_applyai_open_jobs_leaf_id") or "")
        source_url = str(
            payload.get("_applyai_source_url")
            or f"{self.data_base_url}/groups/{leaf_id}.json"
        )
        locations = (location,) if location else ()
        return RawJobPosting(
            source_type=JobSourceType.AUTHORIZED_AGGREGATOR_FEED,
            source_name="open-jobs",
            source_company_identity=f"{ats}:{slug}",
            source_job_identity=external_id,
            external_job_id=external_id,
            internal_job_id=upstream_id,
            source_url=source_url,
            apply_url=apply_url,
            company_name=company_name,
            title=str(payload.get("title") or "").strip(),
            description=description,
            location_text=location or None,
            locations=locations,
            employment_type=normalize_employment_type(None),
            workplace_type=normalize_workplace_type(None, locations),
            seniority="UNKNOWN",
            date_posted=None,
            source_updated_at=seen_at,
            fetched_at=fetched_at,
            raw_payload=payload,
            source_metadata={
                "trust_level": SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED.value,
                "upstream_provider": "OPEN_JOBS",
                "upstream_ats": ats,
                "upstream_board": slug,
                "dataset_license": "CC0-1.0",
                "dataset_role": "DISCOVERY_COVERAGE",
                "closure_authority": False,
            },
        )

    def normalize(self, payload: dict[str, Any]) -> NormalizedJob:
        posting = self.to_raw(payload)
        normalized_payload = dict(posting.raw_payload)
        normalized_payload.update(
            {
                "_applyai_source_type": posting.source_type.value,
                "_applyai_source_name": posting.source_name,
                "_applyai_source_company_identity": posting.source_company_identity,
                "_applyai_source_job_identity": posting.source_job_identity,
                "_applyai_internal_job_id": posting.internal_job_id,
                "_applyai_source_url": posting.source_url,
                "_applyai_source_updated_at": (
                    posting.source_updated_at.isoformat() if posting.source_updated_at else None
                ),
                "_applyai_fetched_at": (
                    posting.fetched_at.isoformat() if posting.fetched_at else None
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
            salary_min=None,
            salary_max=None,
            salary_provenance=None,
            skills=[],
            requirements=[],
            posted_at=None,
            raw_payload=normalized_payload,
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "last_leaf_id": self._last_leaf_id,
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "manifest_recipe": self._manifest_recipe,
            "manifest_jobs": self._manifest_jobs,
            "manifest_leaves": self._manifest_leaves,
            "groups_processed": self._groups_processed,
            "jobs_seen": self._jobs_seen,
            "cycle_complete": self._cycle_complete,
        }

    def health(self) -> ConnectorHealth:
        checked_at = datetime.now(timezone.utc)
        try:
            manifest = self._manifest()
            leaves = self._leaf_ids(manifest)
            if not leaves:
                raise ValueError("manifest contains no leaf groups")
            return ConnectorHealth(
                True,
                checked_at,
                f"Open Jobs public corpus reachable ({len(leaves)} groups)",
            )
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            return ConnectorHealth(
                False,
                checked_at,
                f"Open Jobs health check failed: {type(exc).__name__}",
            )
