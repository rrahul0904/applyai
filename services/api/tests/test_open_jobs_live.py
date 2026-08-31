from __future__ import annotations

import os

import pytest

from app.jobs.open_jobs import OpenJobsConnector


pytestmark = pytest.mark.skipif(
    os.getenv("APPLYAI_RUN_LIVE_OPEN_JOBS_TESTS") != "1",
    reason="set APPLYAI_RUN_LIVE_OPEN_JOBS_TESTS=1 for bounded live Open Jobs acceptance",
)


def test_live_open_jobs_public_corpus_is_reachable_and_normalizes_bounded_records() -> None:
    connector = OpenJobsConnector(
        max_groups_per_run=1,
        max_jobs_per_group=25,
        timeout_seconds=30,
    )
    try:
        health = connector.health()
        assert health.healthy is True

        records = connector.fetch(None)
        assert 0 < len(records) <= 25

        for payload in records[:10]:
            assert payload.get("ats")
            assert payload.get("slug")
            assert payload.get("id") is not None
            assert str(payload.get("title") or "").strip()
            assert str(payload.get("url") or "").startswith("https://")
            assert "v" not in payload

            raw = connector.to_raw(payload)
            normalized = connector.normalize(payload)

            assert raw.source_company_identity == f"{payload['ats']}:{payload['slug']}"
            assert raw.apply_url.startswith("https://")
            assert raw.source_metadata["upstream_provider"] == "OPEN_JOBS"
            assert raw.source_metadata["closure_authority"] is False
            assert normalized.external_job_id == raw.external_job_id
            assert normalized.title == raw.title
            assert normalized.company_name == raw.company_name
            assert "v" not in normalized.raw_payload
    finally:
        connector.close()
