import json

import httpx

from app.jobs.generic_career import CareerSiteJobConnector
from app.jobs.web_security import CrawlBudget, SafeHttpFetcher


def public_resolver(host: str, port: int):
    del host, port
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def test_generic_career_connector_respects_robots_and_extracts_jsonld_job():
    jobposting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Research Data Scientist",
        "description": "Build reproducible research data pipelines and statistical models for biomedical research programs.",
        "identifier": {"value": "REQ-123"},
        "datePosted": "2026-08-01T00:00:00Z",
        "validThrough": "2026-09-01T00:00:00Z",
        "employmentType": "FULL_TIME",
        "hiringOrganization": {
            "name": "Example University",
            "sameAs": "https://example.edu",
        },
        "jobLocation": {
            "address": {
                "addressLocality": "Boston",
                "addressRegion": "MA",
                "addressCountry": "US",
            }
        },
        "url": "https://jobs.example.edu/jobs/research-data-scientist",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path == "/careers":
            return httpx.Response(
                200,
                text='<html><body><a href="/jobs/research-data-scientist">Research Data Scientist</a></body></html>',
            )
        if request.url.path in {"/sitemap.xml", "/sitemap_index.xml", "/jobs-sitemap.xml"}:
            return httpx.Response(404)
        if request.url.path == "/jobs/research-data-scientist":
            return httpx.Response(
                200,
                text=(
                    '<html><head><script type="application/ld+json">'
                    + json.dumps(jobposting)
                    + "</script></head><body><h1>Research Data Scientist</h1></body></html>"
                ),
            )
        return httpx.Response(404)

    fetcher = SafeHttpFetcher(
        budget=CrawlBudget(max_pages=20),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        resolver=public_resolver,
    )
    connector = CareerSiteJobConnector(
        "https://jobs.example.edu/careers",
        source_identity="WORKDAY:jobs.example.edu:root",
        max_pages=20,
        fetcher=fetcher,
    )
    records = connector.fetch(None)
    assert len(records) == 1
    raw = connector.to_raw(records[0])
    assert raw.title == "Research Data Scientist"
    assert raw.company_name == "Example University"
    assert raw.source_company_identity == "WORKDAY:jobs.example.edu:root"
    assert raw.internal_job_id == "REQ-123"
    assert connector.authoritative_snapshot is False


def test_generic_career_connector_blocks_disallowed_robots():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, text="<html></html>")

    fetcher = SafeHttpFetcher(
        budget=CrawlBudget(max_pages=5),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        resolver=public_resolver,
    )
    connector = CareerSiteJobConnector(
        "https://jobs.example.edu/careers",
        source_identity="CAREER_SITE:jobs.example.edu",
        fetcher=fetcher,
    )
    import pytest

    with pytest.raises(ValueError, match="robots policy disallows"):
        connector.fetch(None)
