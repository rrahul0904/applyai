from __future__ import annotations

from types import SimpleNamespace

import httpx

from app.jobs.adapter_factory import create_source_adapter
from app.jobs.contracts import JobSourceType, SourceTrustLevel
from app.jobs.open_jobs import OpenJobsConnector
from app.jobs.source_completeness import CoverageStatus, observed_coverage
from app.jobs.source_pipeline import _record_partial_coverage_health


BASE = "https://open-jobs.test/data"


def _client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/data/manifest.json":
            return httpx.Response(
                200,
                json={
                    "jobs": 3,
                    "leaves": 2,
                    "recipe": "test:1536:v1",
                    "tree": [
                        {"id": 0, "children": [1, 2]},
                        {"id": 1, "children": []},
                        {"id": 2, "children": []},
                    ],
                },
            )
        if request.url.path == "/data/groups/1.json":
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "ats": "greenhouse",
                            "slug": "alpha",
                            "id": "101",
                            "title": "Data Engineer",
                            "company": "Alpha Labs",
                            "location": "Boston, MA",
                            "url": "https://boards.greenhouse.io/alpha/jobs/101",
                            "seen": "2026-08-31T12:00:00Z",
                            "jd": "Build reliable data products.",
                            "v": "embedding-should-not-persist",
                        },
                        {
                            "ats": "lever",
                            "slug": "beta",
                            "id": "202",
                            "title": "Analytics Engineer",
                            "company": "Beta Systems",
                            "location": "Remote",
                            "url": "https://jobs.lever.co/beta/202",
                            "jd": "Own analytics models and quality.",
                            "v": "embedding-should-not-persist",
                        },
                    ]
                },
            )
        if request.url.path == "/data/groups/2.json":
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "ats": "ashby",
                            "slug": "gamma",
                            "id": "303",
                            "title": "ML Engineer",
                            "company": "Gamma AI",
                            "location": "New York, NY",
                            "url": "https://jobs.ashbyhq.com/gamma/303",
                            "jd": "Ship production ML systems.",
                        }
                    ]
                },
            )
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_open_jobs_connector_reads_bounded_leaf_groups_and_advances_checkpoint() -> None:
    connector = OpenJobsConnector(
        data_base_url=BASE,
        max_groups_per_run=1,
        client=_client(),
    )

    first = connector.fetch(None)
    first_checkpoint = connector.checkpoint()

    assert len(first) == 2
    assert {row["company"] for row in first} == {"Alpha Labs", "Beta Systems"}
    assert all("v" not in row for row in first)
    assert first_checkpoint["last_leaf_id"] == "1"
    assert first_checkpoint["manifest_jobs"] == 3
    assert first_checkpoint["cycle_complete"] is False
    assert connector.completeness_checks()["cycle_complete"] is False

    second = connector.fetch(first_checkpoint)
    assert [row["company"] for row in second] == ["Gamma AI"]
    assert connector.checkpoint()["last_leaf_id"] == "2"
    assert connector.checkpoint()["cycle_complete"] is True
    assert connector.completeness_checks()["cycle_complete"] is True
    receipt = observed_coverage(
        connector,
        {"fetched": 1, "failed": 0},
    )
    assert receipt.status is CoverageStatus.PARTIAL
    assert dict(receipt.completeness_checks)["cycle_complete"] is True


def test_open_jobs_restarts_traversal_when_manifest_recipe_changes() -> None:
    connector = OpenJobsConnector(
        data_base_url=BASE,
        max_groups_per_run=1,
        client=_client(),
    )

    rows = connector.fetch(
        {
            "last_leaf_id": "2",
            "manifest_recipe": "older:1536:v1",
            "manifest_leaves": 2,
        }
    )

    assert len(rows) == 2
    assert connector.checkpoint()["last_leaf_id"] == "1"
    assert connector.completeness_checks() == {
        "cycle_complete": False,
        "cycle_restarted_for_manifest_change": True,
    }


def test_open_jobs_advances_only_failure_free_partial_checkpoints() -> None:
    connector = OpenJobsConnector(
        data_base_url=BASE,
        max_groups_per_run=1,
        client=_client(),
    )

    assert connector.checkpoint_advance_safe(
        coverage_status="PARTIAL",
        processing_failures=0,
    )
    assert not connector.checkpoint_advance_safe(
        coverage_status="PARTIAL",
        processing_failures=1,
    )
    assert not connector.checkpoint_advance_safe(
        coverage_status="COMPLETE",
        processing_failures=0,
    )


def test_open_jobs_promotes_legacy_pending_cursor_only_after_success() -> None:
    successful_record = SimpleNamespace(
        configuration={
            "connector_checkpoint": {"last_leaf_id": "1"},
            "open_jobs_pending_checkpoint": {"last_leaf_id": "2"},
            "last_source_completeness_at": "2026-10-14T12:00:00+00:00",
            "last_source_completeness_counts": {"failed": 0},
        }
    )
    connector = OpenJobsConnector(
        data_base_url=BASE,
        max_groups_per_run=1,
        client=_client(),
        source_record=successful_record,
    )

    assert connector._committed_checkpoint(None) == {"last_leaf_id": "2"}
    assert successful_record.configuration["connector_checkpoint"] == {"last_leaf_id": "2"}
    assert "open_jobs_pending_checkpoint" not in successful_record.configuration

    failed_record = SimpleNamespace(
        configuration={
            "connector_checkpoint": {"last_leaf_id": "1"},
            "open_jobs_pending_checkpoint": {"last_leaf_id": "2"},
            "last_source_completeness_at": "2026-10-14T12:00:00+00:00",
            "last_source_completeness_counts": {"failed": 1},
        }
    )
    retry_connector = OpenJobsConnector(
        data_base_url=BASE,
        max_groups_per_run=1,
        client=_client(),
        source_record=failed_record,
    )

    assert retry_connector._committed_checkpoint(None) == {"last_leaf_id": "1"}
    assert failed_record.configuration["connector_checkpoint"] == {"last_leaf_id": "1"}
    assert "open_jobs_pending_checkpoint" not in failed_record.configuration


def test_successful_open_jobs_partial_run_does_not_increment_source_failures() -> None:
    source = SimpleNamespace(
        health_status="DEGRADED",
        consecutive_failures=3,
        last_failure_at="previous failure",
        last_error_category="INCOMPLETE_SOURCE_COVERAGE",
        last_error_summary="Source did not prove complete coverage",
        last_success_at=None,
    )
    connector = OpenJobsConnector(
        data_base_url=BASE,
        max_groups_per_run=1,
        client=_client(),
    )

    _record_partial_coverage_health(source, connector)

    assert source.health_status == "HEALTHY"
    assert source.consecutive_failures == 0
    assert source.last_failure_at is None
    assert source.last_error_category is None
    assert source.last_error_summary is None
    assert source.last_success_at is not None


def test_open_jobs_mapping_preserves_employer_board_identity_and_low_authority_metadata() -> None:
    connector = OpenJobsConnector(data_base_url=BASE, max_groups_per_run=1, client=_client())
    payload = connector.fetch(None)[0]

    raw = connector.to_raw(payload)
    normalized = connector.normalize(payload)

    assert raw.source_type == JobSourceType.AUTHORIZED_AGGREGATOR_FEED
    assert raw.source_company_identity == "greenhouse:alpha"
    assert raw.external_job_id == "greenhouse:alpha:101"
    assert raw.apply_url == "https://boards.greenhouse.io/alpha/jobs/101"
    assert raw.source_metadata["trust_level"] == SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED.value
    assert raw.source_metadata["closure_authority"] is False
    assert raw.source_metadata["dataset_license"] == "CC0-1.0"
    assert normalized.company_name == "Alpha Labs"
    assert normalized.raw_payload["data_origin"] == "OPEN_JOBS_CC0"


def test_adapter_factory_routes_open_jobs_provider_key_to_specialized_connector() -> None:
    source = SimpleNamespace(
        source_type=JobSourceType.AUTHORIZED_AGGREGATOR_FEED.value,
        source_identity="open-jobs",
        base_url=BASE,
        careers_url=None,
        trust_level=SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED.value,
        configuration={
            "provider_key": "OPEN_JOBS",
            "data_base_url": BASE,
            "max_groups_per_run": 1,
        },
    )

    connector = create_source_adapter(source, client=_client())

    assert isinstance(connector, OpenJobsConnector)
    assert connector.authoritative_snapshot is False
