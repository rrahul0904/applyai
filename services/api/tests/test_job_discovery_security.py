import httpx
import pytest

from app.jobs.ats_detector import detect_ats
from app.jobs.career_extractor import extract_career_page
from app.jobs.contracts import JobSourceType, ValidationStatus
from app.jobs.jsonld import parse_jobposting_documents, raw_job_from_jsonld
from app.jobs.robots import AccessPolicy, evaluate_robots
from app.jobs.sitemaps import discover_job_urls_from_sitemaps
from app.jobs.web_security import (
    CrawlBudget,
    CrawlBudgetExceeded,
    PublicUrlRejected,
    SafeHttpFetcher,
    validate_public_http_url,
)


def public_resolver(host: str, port: int):
    del host, port
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def private_resolver(host: str, port: int):
    del host, port
    return [(2, 1, 6, "", ("127.0.0.1", 443))]


def test_public_url_policy_blocks_private_and_unsafe_schemes():
    assert validate_public_http_url(
        "HTTPS://Example.com/jobs/123#apply",
        resolver=public_resolver,
    ) == "https://example.com/jobs/123"

    for value in (
        "http://127.0.0.1/jobs",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "ftp://example.com/jobs",
        "http://user:password@example.com/jobs",
    ):
        with pytest.raises(PublicUrlRejected):
            validate_public_http_url(value, resolver=public_resolver)

    with pytest.raises(PublicUrlRejected):
        validate_public_http_url("https://internal.example/jobs", resolver=private_resolver)


def test_fetcher_revalidates_redirect_destination_and_caps_decompressed_bytes():
    def redirect_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
        raise AssertionError("private redirect should never be fetched")

    fetcher = SafeHttpFetcher(
        client=httpx.Client(transport=httpx.MockTransport(redirect_handler)),
        resolver=public_resolver,
    )
    with pytest.raises(PublicUrlRejected):
        fetcher.fetch("https://example.com/jobs")

    def large_handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, content=b"x" * 65)

    bounded = SafeHttpFetcher(
        budget=CrawlBudget(max_pages=2, max_response_bytes=64),
        client=httpx.Client(transport=httpx.MockTransport(large_handler)),
        resolver=public_resolver,
    )
    with pytest.raises(CrawlBudgetExceeded):
        bounded.fetch("https://example.com/jobs")


def test_robots_allow_and_disallow_are_explicit():
    def allowed_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/robots.txt"
        return httpx.Response(200, text="User-agent: *\nAllow: /jobs\n")

    allowed = evaluate_robots(
        SafeHttpFetcher(
            client=httpx.Client(transport=httpx.MockTransport(allowed_handler)),
            resolver=public_resolver,
        ),
        "https://example.com/jobs/123",
    )
    assert allowed.policy == AccessPolicy.ALLOWED

    def denied_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="User-agent: *\nDisallow: /jobs\n")

    denied = evaluate_robots(
        SafeHttpFetcher(
            client=httpx.Client(transport=httpx.MockTransport(denied_handler)),
            resolver=public_resolver,
        ),
        "https://example.com/jobs/123",
    )
    assert denied.policy == AccessPolicy.DISALLOWED


def test_ats_detector_recognizes_supported_and_enterprise_platforms():
    assert detect_ats("https://jobs.lever.co/example/abc").provider == JobSourceType.LEVER
    assert detect_ats("https://jobs.ashbyhq.com/example/abc").provider == JobSourceType.ASHBY
    assert detect_ats("https://boards.greenhouse.io/example/jobs/1").provider == JobSourceType.GREENHOUSE
    assert detect_ats("https://example.wd5.myworkdayjobs.com/jobs").provider == JobSourceType.WORKDAY
    assert detect_ats("https://careers.smartrecruiters.com/example").provider == JobSourceType.SMARTRECRUITERS
    detected = detect_ats(
        "https://example.com/careers",
        '<iframe src="https://jobs.icims.com/jobs/123"></iframe>',
    )
    assert detected.provider == JobSourceType.ICIMS
    assert detected.evidence


def test_sitemap_discovery_is_bounded_and_filters_job_paths():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                text="""<?xml version='1.0'?><urlset>
                <url><loc>https://example.com/jobs/data-engineer</loc></url>
                <url><loc>https://example.com/about</loc></url>
                <url><loc>https://example.com/careers/platform-engineer</loc></url>
                </urlset>""",
                headers={"Content-Type": "application/xml"},
            )
        return httpx.Response(404)

    result = discover_job_urls_from_sitemaps(
        SafeHttpFetcher(
            budget=CrawlBudget(max_pages=4),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            resolver=public_resolver,
        ),
        "https://example.com",
        max_sitemaps=1,
    )
    assert result.candidate_job_urls == (
        "https://example.com/jobs/data-engineer",
        "https://example.com/careers/platform-engineer",
    )


def jobposting_html() -> str:
    return """
    <html><head><script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "Senior Data Engineer",
      "description": "<p>Build reliable data systems and production analytics platforms for customers.</p>",
      "datePosted": "2026-07-30",
      "validThrough": "2026-09-30T23:59:59Z",
      "employmentType": "FULL_TIME",
      "identifier": {"value": "REQ-123"},
      "hiringOrganization": {"name": "Example Labs", "sameAs": "https://example.com"},
      "jobLocationType": "TELECOMMUTE",
      "applicantLocationRequirements": {"name": "United States"},
      "baseSalary": {
        "currency": "USD",
        "value": {"minValue": 150000, "maxValue": 190000, "unitText": "YEAR"}
      },
      "url": "https://example.com/jobs/req-123"
    }
    </script></head><body><h1>Senior Data Engineer</h1></body></html>
    """


def test_jsonld_jobposting_is_preferred_and_preserved():
    nodes = parse_jobposting_documents(jobposting_html())
    assert len(nodes) == 1
    raw = raw_job_from_jsonld(nodes[0], page_url="https://example.com/jobs/req-123")
    assert raw.title == "Senior Data Engineer"
    assert raw.company_name == "Example Labs"
    assert raw.workplace_type == "REMOTE"
    assert raw.locations == ("United States",)
    assert raw.salary_min == 150000
    assert raw.salary_max == 190000
    assert raw.internal_job_id == "REQ-123"
    assert raw.raw_payload["@type"] == "JobPosting"

    extracted = extract_career_page(
        jobposting_html(),
        page_url="https://example.com/jobs/req-123",
    )
    assert extracted.status == ValidationStatus.VALID
    assert extracted.posting is not None


def test_generic_extractor_quarantines_listing_pages():
    listing = """
    <html><body><h1>Open jobs</h1>
    <a href="/jobs/1/apply">Apply</a>
    <a href="/jobs/2/apply">Apply</a>
    <a href="/jobs/3/apply">Apply</a>
    <a href="/jobs/4/apply">Apply</a>
    <p>Browse all current openings across our teams and locations.</p>
    </body></html>
    """
    result = extract_career_page(listing, page_url="https://example.com/jobs")
    assert result.status == ValidationStatus.QUARANTINED
    assert result.posting is None
