import httpx

from app.jobs.connectors import GreenhouseJobBoardConnector


def greenhouse_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/boards/example":
        return httpx.Response(200, json={"name": "Example Labs"})
    if request.url.path == "/v1/boards/example/jobs":
        assert request.url.params.get("content") == "true"
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 127817,
                        "title": "Senior Data Engineer",
                        "updated_at": "2026-07-25T10:55:28-05:00",
                        "location": {"name": "Remote - United States"},
                        "absolute_url": "https://boards.greenhouse.io/example/jobs/127817",
                        "content": "&lt;p&gt;Build reliable data platforms.&lt;/p&gt;",
                        "offices": [
                            {
                                "id": 1,
                                "name": "Boston",
                                "location": "Boston, MA, United States",
                            }
                        ],
                    }
                ],
                "meta": {"total": 1},
            },
        )
    return httpx.Response(404)


def test_greenhouse_fetch_and_normalize_public_job_board():
    client = httpx.Client(transport=httpx.MockTransport(greenhouse_handler))
    connector = GreenhouseJobBoardConnector("example", client=client)

    records = connector.fetch(None)
    assert len(records) == 1
    assert records[0]["data_origin"] == "GREENHOUSE_PUBLIC_API"
    assert records[0]["_applyai_company_name"] == "Example Labs"

    job = connector.normalize(records[0])
    assert job.external_job_id == "127817"
    assert job.company_name == "Example Labs"
    assert job.title == "Senior Data Engineer"
    assert job.application_url == "https://boards.greenhouse.io/example/jobs/127817"
    assert job.locations == ["Remote - United States", "Boston, MA, United States"]
    assert job.work_mode == "REMOTE"
    assert job.employment_type == "UNKNOWN"
    assert job.seniority == "UNKNOWN"
    assert job.description == "Build reliable data platforms."
    assert job.posted_at is None
    assert connector.checkpoint()["count"] == 1


def test_greenhouse_health_uses_public_board_endpoint():
    client = httpx.Client(transport=httpx.MockTransport(greenhouse_handler))
    connector = GreenhouseJobBoardConnector("example", client=client)

    health = connector.health()
    assert health.healthy is True
    assert "reachable" in health.detail


def test_greenhouse_rejects_unsafe_board_token():
    try:
        GreenhouseJobBoardConnector("../secret")
    except ValueError as exc:
        assert "invalid" in str(exc).lower()
    else:
        raise AssertionError("unsafe board token should be rejected")
