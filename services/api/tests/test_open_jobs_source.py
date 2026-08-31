from __future__ import annotations

from types import SimpleNamespace

import httpx

from app.jobs.adapter_factory import create_source_adapter
from app.jobs.contracts import JobSourceType, SourceTrustLevel
from app.jobs.open_jobs import OpenJobsConnector


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

    second = connector.fetch(first_checkpoint)
    assert [row["company"] for row in second] == ["Gamma AI"]
    assert connector.checkpoint()["last_leaf_id"] == "2"
    assert connector.checkpoint()["cycle_complete"] is True


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
