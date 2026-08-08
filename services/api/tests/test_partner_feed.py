import json

import httpx

from app.jobs.contracts import JobSourceType, SourceTrustLevel
from app.jobs.partner_feed import PartnerFeedConnector
from app.jobs.web_security import CrawlBudget, SafeHttpFetcher


def public_resolver(host: str, port: int):
    del host, port
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def fetcher_for(content: bytes, content_type: str) -> SafeHttpFetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=content,
            headers={"Content-Type": content_type, "ETag": '"v1"'},
            request=request,
        )

    return SafeHttpFetcher(
        budget=CrawlBudget(max_pages=1, max_response_bytes=1024 * 1024),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        resolver=public_resolver,
    )


def test_authorized_json_feed_maps_configured_fields_and_provenance():
    payload = {
        "jobs": [
            {
                "job_id": "REQ-42",
                "role": "Senior Data Engineer",
                "employer": "Example Labs",
                "body": "Build reliable production data platforms for customer-facing analytics services.",
                "apply": "https://jobs.example.com/req-42/apply",
                "page": "https://jobs.example.com/req-42",
                "place": "Remote - United States",
                "posted": "2026-08-01T12:00:00Z",
            }
        ]
    }
    connector = PartnerFeedConnector(
        feed_url="https://feeds.example.com/jobs.json",
        source_identity="example-feed",
        provider_key="partner-example",
        feed_format="json",
        field_map={
            "id": "job_id",
            "title": "role",
            "company": "employer",
            "description": "body",
            "apply_url": "apply",
            "source_url": "page",
            "location": "place",
            "posted_at": "posted",
            "requisition_id": "job_id",
        },
        source_type=JobSourceType.AUTHORIZED_AGGREGATOR_FEED,
        trust_level=SourceTrustLevel.LICENSED_FEED,
        authoritative_snapshot=True,
        fetcher=fetcher_for(json.dumps(payload).encode(), "application/json"),
    )
    rows = connector.fetch(None)
    raw = connector.to_raw(rows[0])
    normalized = connector.normalize(rows[0])

    assert raw.external_job_id == "partner-example:example-feed:REQ-42"
    assert raw.internal_job_id == "REQ-42"
    assert raw.company_name == "Example Labs"
    assert raw.locations == ("Remote - United States",)
    assert raw.source_metadata["trust_level"] == "LICENSED_FEED"
    assert normalized.raw_payload["data_origin"] == "AUTHORIZED_LICENSED_FEED"
    assert connector.authoritative_snapshot is True
    assert connector.checkpoint()["etag"] == '"v1"'


def test_authorized_xml_feed_parses_rss_items():
    xml = b"""<?xml version='1.0'?>
    <rss><channel><item>
      <id>job-1</id>
      <title>Research Analyst</title>
      <company>Example Foundation</company>
      <description>Conduct rigorous research and analysis for public-interest programs and reports.</description>
      <link>https://jobs.example.org/job-1</link>
      <location>Boston, MA</location>
    </item></channel></rss>"""
    connector = PartnerFeedConnector(
        feed_url="https://feeds.example.org/jobs.xml",
        source_identity="foundation-feed",
        provider_key="licensed-foundation",
        feed_format="xml",
        field_map={"apply_url": "link", "source_url": "link"},
        fetcher=fetcher_for(xml, "application/rss+xml"),
    )
    rows = connector.fetch(None)
    assert len(rows) == 1
    raw = connector.to_raw(rows[0])
    assert raw.title == "Research Analyst"
    assert raw.company_name == "Example Foundation"
    assert raw.apply_url == "https://jobs.example.org/job-1"
