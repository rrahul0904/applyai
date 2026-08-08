import httpx

from app.jobs.contracts import SourceTrustLevel
from app.jobs.smartrecruiters import SmartRecruitersPostingConnector


def test_smartrecruiters_public_posting_api_fetch_and_normalize():
    list_payload = {
        "offset": 0,
        "limit": 100,
        "totalFound": 1,
        "content": [
            {
                "id": "74983486",
                "uuid": "34225731-e7cf-4584-b0b7-78098fe1a66b",
                "name": "Senior Data Engineer",
            }
        ],
    }
    detail_payload = {
        "id": "74983486",
        "uuid": "34225731-e7cf-4584-b0b7-78098fe1a66b",
        "jobId": "job-123",
        "name": "Senior Data Engineer",
        "company": {"identifier": "example", "name": "Example Corp"},
        "releasedDate": "2026-08-01T10:00:00Z",
        "location": {"city": "Boston", "region": "MA", "country": "US", "remote": True},
        "typeOfEmployment": {"label": "Full-time"},
        "experienceLevel": {"label": "Mid-Senior Level"},
        "applyUrl": "https://jobs.smartrecruiters.com/example/74983486/apply",
        "jobAd": {
            "sections": {
                "jobDescription": {
                    "text": "Build reliable data platforms, streaming systems, and production analytics infrastructure for enterprise teams."
                },
                "qualifications": {
                    "text": "Strong Python, SQL, distributed systems, and cloud data engineering experience required."
                },
            }
        },
        "department": {"label": "Data"},
        "function": {"label": "Engineering"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/postings"):
            return httpx.Response(200, json=list_payload)
        if request.url.path.endswith("/postings/34225731-e7cf-4584-b0b7-78098fe1a66b"):
            return httpx.Response(200, json=detail_payload)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = SmartRecruitersPostingConnector(
        "example",
        client=client,
        request_interval_seconds=0,
    )
    records = connector.fetch(None)
    assert len(records) == 1
    assert connector.authoritative_snapshot is True
    raw = connector.to_raw(records[0])
    assert raw.external_job_id == "example:34225731-e7cf-4584-b0b7-78098fe1a66b"
    assert raw.company_name == "Example Corp"
    assert raw.workplace_type == "REMOTE"
    assert raw.source_metadata["trust_level"] == SourceTrustLevel.OFFICIAL_ATS.value
    normalized = connector.normalize(records[0])
    assert normalized.title == "Senior Data Engineer"
    assert normalized.employment_type == "FULL_TIME"
