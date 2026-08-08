import httpx

from app.jobs.contracts import SourceTrustLevel
from app.jobs.public_feeds import ReliefWebJobsConnector, USAJobsConnector


def test_usajobs_connector_fetches_and_normalizes_official_posting():
    payload = {
        "SearchResult": {
            "SearchResultCountAll": 1,
            "SearchResultItems": [
                {
                    "MatchedObjectId": "12345",
                    "MatchedObjectDescriptor": {
                        "PositionID": "12345",
                        "PositionTitle": "Data Scientist",
                        "PositionURI": "https://www.usajobs.gov/job/12345",
                        "ApplyURI": ["https://www.usajobs.gov/apply/12345"],
                        "OrganizationName": "National Institutes of Health",
                        "DepartmentName": "Department of Health and Human Services",
                        "PositionLocation": [{"LocationName": "Montgomery County, Maryland"}],
                        "PositionRemuneration": [
                            {"MinimumRange": "120000", "MaximumRange": "160000"}
                        ],
                        "PublicationStartDate": "2026-08-01T00:00:00Z",
                        "ApplicationCloseDate": "2026-08-15T23:59:59Z",
                        "QualificationSummary": "Applicants must have substantial data science experience and statistical programming expertise.",
                        "UserArea": {
                            "Details": {
                                "JobSummary": "Support biomedical research with reproducible data science and analytics.",
                                "MajorDuties": "Build analytical systems, evaluate evidence, and collaborate with research teams.",
                                "Requirements": "US citizenship requirements are defined in the official announcement.",
                                "SecurityClearance": "Not Required",
                                "RemoteIndicator": True,
                                "WhoMayApply": {"Name": "The public"},
                            }
                        },
                    },
                }
            ],
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization-Key"] == "test-key"
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = USAJobsConnector(api_key="test-key", user_agent="test@example.com", client=client)
    records = connector.fetch(None)
    assert len(records) == 1
    raw = connector.to_raw(records[0])
    assert raw.external_job_id == "usajobs:12345"
    assert raw.company_name == "National Institutes of Health"
    assert raw.workplace_type == "REMOTE"
    assert raw.salary_min == 120000
    assert raw.salary_max == 160000
    assert raw.source_metadata["trust_level"] == SourceTrustLevel.GOVERNMENT_OFFICIAL.value
    normalized = connector.normalize(records[0])
    assert normalized.title == "Data Scientist"
    assert normalized.application_url == "https://www.usajobs.gov/apply/12345"


def test_reliefweb_connector_fetches_and_normalizes_humanitarian_posting():
    payload = {
        "totalCount": 1,
        "data": [
            {
                "id": "98765",
                "fields": {
                    "title": "Monitoring and Evaluation Specialist",
                    "body": "<p>Lead monitoring, evaluation, learning, research, and evidence activities for humanitarian programs.</p>",
                    "url": "https://reliefweb.int/job/98765/example",
                    "url_alias": "https://reliefweb.int/job/98765/example",
                    "source": [{"name": "Example Humanitarian NGO"}],
                    "country": [{"name": "Kenya"}],
                    "job_type": [{"name": "Full-time"}],
                    "date": {
                        "created": "2026-08-01T10:00:00Z",
                        "closing": "2026-08-20T23:59:59Z",
                    },
                    "career_categories": [{"name": "Monitoring and Evaluation"}],
                },
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["appname"] == "applyai-test"
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = ReliefWebJobsConnector(appname="applyai-test", client=client)
    records = connector.fetch(None)
    assert len(records) == 1
    raw = connector.to_raw(records[0])
    assert raw.external_job_id == "reliefweb:98765"
    assert raw.company_name == "Example Humanitarian NGO"
    assert raw.locations == ("Kenya",)
    assert raw.source_metadata["trust_level"] == SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED.value
    normalized = connector.normalize(records[0])
    assert normalized.title == "Monitoring and Evaluation Specialist"
    assert "humanitarian programs" in normalized.description
