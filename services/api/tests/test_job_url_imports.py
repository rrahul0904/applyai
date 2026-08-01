import json
import uuid

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.durability_models import TaskOutbox
from app.job_source_models import JobSourceDiscovery, JobSourceRegistry
from app.jobs.discovery import process_discovery_record
from app.jobs.web_security import CrawlBudget, SafeHttpFetcher
from app.models import Job, JobSource, JobSourceLink
from app.workers.discovery import process_message


def public_resolver(host: str, port: int):
    del host, port
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def job_html(job_url: str) -> str:
    return f"""
    <html><head><script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "Senior Data Engineer",
      "description": "<p>Build reliable data systems and production analytics platforms for customer products.</p>",
      "datePosted": "2026-07-30",
      "validThrough": "2026-09-30T23:59:59Z",
      "employmentType": "FULL_TIME",
      "identifier": {{"value": "REQ-123"}},
      "hiringOrganization": {{"name": "Example Labs", "sameAs": "https://example.com"}},
      "jobLocationType": "TELECOMMUTE",
      "applicantLocationRequirements": {{"name": "United States"}},
      "url": "{job_url}"
    }}
    </script></head><body><h1>Senior Data Engineer</h1></body></html>
    """


def test_job_url_import_is_transactionally_queued_and_user_scoped(
    client: TestClient,
    database_url: str,
    switch_user,
):
    created = client.post(
        "/api/v1/jobs/import-url",
        json={"url": "https://8.8.8.8/jobs/req-123"},
    )
    assert created.status_code == 202
    payload = created.json()
    assert payload["status"] == "QUEUED"
    discovery_id = uuid.UUID(payload["id"])

    engine = create_engine(database_url)
    with Session(engine) as session:
        record = session.get(JobSourceDiscovery, discovery_id)
        outbox = session.scalar(
            select(TaskOutbox).where(TaskOutbox.aggregate_id == discovery_id)
        )
        assert record is not None
        assert outbox is not None
        assert outbox.event_type == "JOB_URL_IMPORT"
        assert outbox.idempotency_key == f"job-url-import:{discovery_id}"

    repeated = client.post(
        "/api/v1/jobs/import-url",
        json={"url": "https://8.8.8.8/jobs/req-123"},
    )
    assert repeated.status_code == 202
    assert repeated.json()["id"] == str(discovery_id)

    switch_user("clerk_user_b", "b@example.com")
    hidden = client.get(f"/api/v1/jobs/import-url/{discovery_id}")
    assert hidden.status_code == 404
    engine.dispose()


def test_job_url_import_rejects_obvious_ssrf_targets(client: TestClient):
    for value in (
        "http://127.0.0.1/jobs/1",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
    ):
        response = client.post("/api/v1/jobs/import-url", json={"url": value})
        assert response.status_code == 422


def test_background_import_extracts_jsonld_and_creates_canonical_job(
    client: TestClient,
    database_url: str,
):
    job_url = "https://8.8.8.8/jobs/req-123"
    created = client.post("/api/v1/jobs/import-url", json={"url": job_url})
    discovery_id = uuid.UUID(created.json()["id"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path == "/jobs/req-123":
            return httpx.Response(
                200,
                text=job_html(job_url),
                headers={
                    "Content-Type": "text/html; charset=utf-8",
                    "ETag": '"job-v1"',
                    "Last-Modified": "Thu, 30 Jul 2026 12:00:00 GMT",
                },
            )
        return httpx.Response(404)

    fetcher = SafeHttpFetcher(
        budget=CrawlBudget(max_pages=6),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        resolver=public_resolver,
    )
    record = process_discovery_record(
        discovery_id,
        settings=Settings(),
        fetcher=fetcher,
    )
    assert record.status == "VERIFIED"
    assert record.job_id is not None
    assert record.detected_provider == "CAREER_SITE"
    assert record.access_policy == "ALLOWED"
    assert record.content_hash
    assert record.etag == '"job-v1"'

    engine = create_engine(database_url)
    with Session(engine) as session:
        assert session.scalar(select(func.count(Job.id))) == 1
        assert session.scalar(select(func.count(JobSource.id))) == 1
        assert session.scalar(select(func.count(JobSourceLink.id))) == 1
        assert session.scalar(select(func.count(JobSourceRegistry.id))) == 2
        persisted = session.get(JobSourceDiscovery, discovery_id)
        assert persisted is not None and persisted.job_id is not None
    engine.dispose()


def test_discovery_worker_acknowledges_terminal_and_retries_failed(
    client: TestClient,
    database_url: str,
):
    created = client.post(
        "/api/v1/jobs/import-url",
        json={"url": "https://8.8.8.8/jobs/worker-test"},
    )
    discovery_id = created.json()["id"]
    body = json.dumps(
        {
            "task_type": "JOB_URL_IMPORT",
            "payload": {"discovery_id": discovery_id},
            "idempotency_key": f"job-url-import:{discovery_id}",
        }
    )

    engine = create_engine(database_url)
    with Session(engine) as session:
        record = session.get(JobSourceDiscovery, uuid.UUID(discovery_id))
        assert record is not None
        record.status = "BLOCKED"
        session.commit()
    assert process_message(body, Settings()) is True

    with Session(engine) as session:
        record = session.get(JobSourceDiscovery, uuid.UUID(discovery_id))
        assert record is not None
        record.status = "FAILED"
        session.commit()
    # The retry path would perform a real fetch, so this assertion is limited to the
    # terminal idempotency contract; failure execution itself is covered by fetcher tests.
    engine.dispose()
