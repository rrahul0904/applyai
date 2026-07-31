import uuid

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.job_source_models import JobSourceDiscovery, JobSourceRegistry
from app.jobs.company_discovery import process_company_discovery_record
from app.jobs.web_security import CrawlBudget, SafeHttpFetcher


def public_resolver(host: str, port: int):
    del host, port
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def test_operator_queues_company_discovery_and_registers_detected_lever_source(
    client: TestClient,
    database_url: str,
):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        internal_api_token="operator-token-at-least-24-characters"
    )
    headers = {"X-ApplyAI-Internal-Token": "operator-token-at-least-24-characters"}
    queued = client.post(
        "/api/v1/internal/job-source-discoveries",
        headers=headers,
        json={"url": "https://8.8.8.8"},
    )
    assert queued.status_code == 202
    discovery_id = uuid.UUID(queued.json()["id"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.host == "8.8.8.8" and request.url.path == "/":
            return httpx.Response(
                200,
                text='<html><body><a href="https://jobs.lever.co/example">Careers</a></body></html>',
            )
        if request.url.host == "jobs.lever.co":
            return httpx.Response(200, text="<html><body><h1>Example careers</h1></body></html>")
        return httpx.Response(404)

    record = process_company_discovery_record(
        discovery_id,
        settings=Settings(career_discovery_max_pages=8),
        fetcher=SafeHttpFetcher(
            budget=CrawlBudget(max_pages=8),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            resolver=public_resolver,
        ),
    )
    assert record.status == "VERIFIED"
    assert record.detected_provider == "LEVER"
    assert record.discovered_careers_url == "https://jobs.lever.co/example"
    assert record.source_registry_id is not None

    engine = create_engine(database_url)
    with Session(engine) as session:
        source = session.scalar(select(JobSourceRegistry))
        assert source is not None
        assert source.source_type == "LEVER"
        assert source.source_identity == "example"
        assert source.enabled is True
        persisted = session.get(JobSourceDiscovery, discovery_id)
        assert persisted is not None and persisted.access_policy == "ALLOWED"
    engine.dispose()
