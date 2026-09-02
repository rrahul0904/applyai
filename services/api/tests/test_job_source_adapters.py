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
from app.jobs.pipeline import MAX_JOB_LOCATION_TEXT_LENGTH, bounded_job_locations


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
    assert validate_raw_job(raw).accepted is True


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
