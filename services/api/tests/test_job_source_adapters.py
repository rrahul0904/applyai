import httpx

from app.job_source_models import JobSourceRegistry
from app.jobs.adapters import (
    AshbyJobBoardConnector,
    JobSourceAdapterFactory,
    LeverJobPostingConnector,
)
from app.jobs.contracts import (
    JobSourceType,
    RawJobPosting,
    ValidationStatus,
    canonicalize_public_url,
    normalize_employment_type,
    normalize_title,
    validate_raw_job,
)
from app.jobs.partner_feed import PartnerFeedConnector
from app.jobs.pipeline import MAX_JOB_LOCATION_TEXT_LENGTH, bounded_job_locations
from app.api.internal_job_sources import _ImportedGreenhousePayloadConnector
from app.jobs.source_completeness import SourceCompleteness, connector_completeness


def lever_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/v0/postings/example"
    assert request.url.params.get("mode") == "json"
    assert request.url.params.get("limit") in {"1", "100"}
    return httpx.Response(
        200,
        json=[
            {
                "id": "lever-posting-1",
                "text": "Senior Data Engineer",
                "categories": {
                    "location": "Boston, MA",
                    "allLocations": ["Boston, MA", "Remote - US"],
                    "commitment": "Full-time",
                    "team": "Data",
                    "department": "Engineering",
                    "level": "Senior",
                },
                "country": "US",
                "descriptionPlain": (
                    "Build reliable production data platforms and streaming systems "
                    "for customer-facing analytics products."
                ),
                "lists": [
                    {"text": "Requirements", "content": "<li>Python and SQL</li>"}
                ],
                "hostedUrl": "https://jobs.lever.co/example/lever-posting-1",
                "applyUrl": "https://jobs.lever.co/example/lever-posting-1/apply",
                "workplaceType": "hybrid",
                "remote_scope": "WORLDWIDE",
                "eligible_countries": [],
                "eligible_regions": [],
                "tags": ["Data Platform", "Python", "python"],
                "updatedAt": "2026-08-01T10:00:00Z",
                "salaryRange": {
                    "min": 150000,
                    "max": 190000,
                    "currency": "USD",
                    "interval": "year",
                },
            }
        ],
    )


def ashby_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/posting-api/job-board/example"
    return httpx.Response(
        200,
        json={
            "apiVersion": "1",
            "jobs": [
                {
                    "id": "ashby-posting-1",
                    "jobId": "requisition-88",
                    "title": "Staff Platform Engineer",
                    "location": "New York, NY",
                    "secondaryLocations": [{"location": "Remote - United States"}],
                    "department": "Engineering",
                    "team": "Infrastructure",
                    "employmentType": "Full-time",
                    "seniority": "Principal",
                    "remote_scope": "COUNTRY_RESTRICTED",
                    "eligible_countries": ["US"],
                    "tags": ["Platform Engineering", "Kubernetes"],
                    "isRemote": True,
                    "descriptionPlain": (
                        "Design resilient application platforms and deployment systems "
                        "used by engineering teams across the company."
                    ),
                    "jobUrl": "https://jobs.ashbyhq.com/example/ashby-posting-1",
                    "applyUrl": "https://jobs.ashbyhq.com/example/ashby-posting-1/application",
                    "publishedAt": "2026-07-30T12:00:00Z",
                    "compensation": {
                        "minimum": 210000,
                        "maximum": 260000,
                        "currency": "USD",
                        "interval": "YEAR",
                    },
                }
            ],
        },
    )


def test_lever_public_postings_connector_preserves_provenance():
    client = httpx.Client(transport=httpx.MockTransport(lever_handler))
    connector = LeverJobPostingConnector("example", company_name="Example Labs", client=client)

    records = connector.fetch(None)
    assert len(records) == 1
    raw = connector.to_raw(records[0])
    normalized = connector.normalize(records[0])

    assert raw.source_type == JobSourceType.LEVER
    assert raw.source_company_identity == "example"
    assert raw.source_job_identity == "example:lever-posting-1"
    assert raw.source_url.endswith("lever-posting-1")
    assert raw.apply_url.endswith("/apply")
    assert raw.locations == ("Boston, MA", "Remote - US")
    assert raw.workplace_type == "HYBRID"
    assert raw.employment_type == "FULL_TIME"
    assert raw.salary_min == 150000
    assert raw.salary_max == 190000
    assert raw.source_metadata["team"] == "Data"
    assert raw.source_metadata["remote_scope"] == "WORLDWIDE"
    assert raw.source_metadata["source_url"] == raw.source_url
    assert raw.source_metadata["application_url"] == raw.apply_url
    assert raw.source_metadata["tags"] == ("DATA_PLATFORM", "PYTHON")
    assert raw.source_updated_at is not None
    assert raw.seniority == "SENIOR"
    assert normalized.external_job_id == "example:lever-posting-1"
    assert validate_raw_job(raw).status == ValidationStatus.VALID


def test_ashby_public_board_connector_preserves_secondary_locations_and_salary():
    client = httpx.Client(transport=httpx.MockTransport(ashby_handler))
    connector = AshbyJobBoardConnector("example", company_name="Example Labs", client=client)

    records = connector.fetch(None)
    assert len(records) == 1
    raw = connector.to_raw(records[0])

    assert raw.source_type == JobSourceType.ASHBY
    assert raw.external_job_id == "example:ashby-posting-1"
    assert raw.internal_job_id == "requisition-88"
    assert raw.locations == ("New York, NY", "Remote - United States")
    assert raw.workplace_type == "REMOTE"
    assert raw.employment_type == "FULL_TIME"
    assert raw.salary_min == 210000
    assert raw.salary_max == 260000
    assert raw.date_posted is not None
    assert raw.seniority == "PRINCIPAL"
    assert raw.source_metadata["eligible_countries"] == ("US",)
    assert raw.source_metadata["tags"] == ("PLATFORM_ENGINEERING", "KUBERNETES")
    assert validate_raw_job(raw).accepted is True


def test_authorized_aggregator_feed_preserves_remote_source_and_salary_evidence():
    connector = PartnerFeedConnector(
        feed_url="https://feed.example/jobs.json",
        source_identity="licensed-remote-jobs",
        provider_key="remoteitjobs",
        field_map={"source_updated_at": "updated_at", "seniority": "level", "tags": "facets"},
    )
    raw = connector.to_raw({
        "id": "remote-123",
        "title": "Senior Data Engineer",
        "company": "Example Labs",
        "description": "Build and maintain production data systems for product teams.",
        "url": "https://remoteitjobs.example/jobs/remote-123",
        "apply_url": "https://jobs.example/apply/remote-123",
        "location": "Remote - EEA",
        "workplace_type": "remote",
        "employment_type": "Full-time",
        "level": "Senior",
        "remote_scope": "REGION_RESTRICTED",
        "eligible_regions": ["EEA"],
        "eligible_countries": [],
        "facets": ["Data Platform", "Python", "python"],
        "salary_min": "120000",
        "salary_max": "150000",
        "salary_currency": "EUR",
        "salary_interval": "YEAR",
        "date_posted": "2026-09-30T12:00:00Z",
        "updated_at": "2026-10-01T09:30:00Z",
    })

    assert raw.source_type == JobSourceType.AUTHORIZED_AGGREGATOR_FEED
    assert raw.source_metadata["provider_key"] == "remoteitjobs"
    assert raw.source_metadata["trust_level"] == "AUTHORIZED_AGGREGATOR_FEED"
    assert raw.source_metadata["remote_scope"] == "REGION_RESTRICTED"
    assert raw.source_metadata["eligible_regions"] == ("EEA",)
    assert raw.source_metadata["remote_restriction_provenance"]["source_field"] == "remote_scope"
    assert raw.source_metadata["source_url"] == raw.source_url
    assert raw.source_metadata["application_url"] == raw.apply_url
    assert raw.source_metadata["tags"] == ("DATA_PLATFORM", "PYTHON")
    assert raw.skills == ()
    assert raw.employment_type == "FULL_TIME"
    assert raw.seniority == "SENIOR"
    assert raw.source_updated_at is not None
    assert raw.date_posted is not None
    assert raw.salary_provenance == "SOURCE_REPORTED"


def test_partner_feed_does_not_infer_remote_scope_from_remote_label():
    connector = PartnerFeedConnector(
        feed_url="https://feed.example/jobs.json",
        source_identity="licensed-feed",
        provider_key="licensed-remote",
    )
    raw = connector.to_raw({
        "id": "unknown-remote-1",
        "title": "Backend Engineer",
        "company": "Example Labs",
        "description": "Build backend services supporting customer workflows.",
        "url": "https://feed.example/jobs/unknown-remote-1",
        "location": "Remote",
        "workplace_type": "remote",
    })

    assert raw.workplace_type == "REMOTE"
    assert raw.source_metadata["remote_scope"] is None
    assert raw.source_metadata["eligible_countries"] == ()
    assert raw.source_metadata["eligible_regions"] == ()
    assert raw.seniority == "UNKNOWN"


def test_adapter_factory_routes_registry_source_without_scattered_conditionals():
    lever_source = JobSourceRegistry(
        source_type="LEVER",
        source_name="Example Lever",
        source_identity="example",
        configuration={"site": "example", "company_name": "Example Labs"},
    )
    ashby_source = JobSourceRegistry(
        source_type="ASHBY",
        source_name="Example Ashby",
        source_identity="example",
        configuration={"board_name": "example", "company_name": "Example Labs"},
    )

    assert isinstance(JobSourceAdapterFactory.create(lever_source), LeverJobPostingConnector)
    assert isinstance(JobSourceAdapterFactory.create(ashby_source), AshbyJobBoardConnector)


def test_job_location_is_bounded_before_canonical_persistence():
    oversized = "Remote, " + ("United States; " * 40)

    locations = bounded_job_locations([oversized, "Remote"])

    assert len(locations[0]) == MAX_JOB_LOCATION_TEXT_LENGTH
    assert locations[0].endswith("…")
    assert locations[1] == "Remote"


def test_imported_greenhouse_payload_preserves_official_source_metadata():
    connector = _ImportedGreenhousePayloadConnector(
        board_token="example",
        company_name="Example Labs",
        postings=[
            {
                "id": 101,
                "internal_job_id": 77,
                "title": "Data Engineer",
                "absolute_url": "https://boards.greenhouse.io/example/jobs/101",
                "content": "Build production data systems.",
                "updated_at": "2026-09-01T00:00:00Z",
            }
        ],
    )

    record = connector.fetch(None)[0]

    assert record["_applyai_company_name"] == "Example Labs"
    assert record["_applyai_board_token"] == "example"
    assert record["_applyai_internal_job_id"] == "77"
    assert record["data_origin"] == "GREENHOUSE_PUBLIC_API"
    assert connector_completeness(connector) == SourceCompleteness.PARTIAL


def test_normalization_and_validation_are_conservative_and_explainable():
    assert normalize_title("Sr. Software Engineer") == "senior software engineer"
    assert normalize_title("Software Engineer, Senior") == "software engineer senior"
    assert normalize_employment_type("Intern") == "INTERNSHIP"
    assert canonicalize_public_url(
        "HTTPS://Example.com/jobs/123/?utm_source=feed&department=data#apply"
    ) == "https://example.com/jobs/123?department=data"

    invalid = RawJobPosting(
        source_type=JobSourceType.JSON_FEED,
        source_name="feed",
        source_company_identity="example",
        source_job_identity="bad-1",
        external_job_id="bad-1",
        company_name="Example Labs",
        title="-",
        description="short",
        source_url="not-a-url",
        apply_url="file:///tmp/apply",
    )
    result = validate_raw_job(invalid)
    assert result.status == ValidationStatus.INVALID
    assert "TITLE_MISSING_OR_PLACEHOLDER" in result.errors
    assert "DESCRIPTION_TOO_SHORT" in result.errors
    assert "SOURCE_URL_INVALID" in result.errors
    assert "APPLY_URL_INVALID" in result.errors
