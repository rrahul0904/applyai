import httpx

from app.jobs.contracts import IngestionErrorCategory, classify_ingestion_error


def _http_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.test/jobs")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("upstream response", request=request, response=response)


def test_classifies_provider_http_status_failures():
    assert classify_ingestion_error(_http_error(429)) is IngestionErrorCategory.RATE_LIMITED
    assert classify_ingestion_error(_http_error(401)) is IngestionErrorCategory.AUTH_REQUIRED
    assert classify_ingestion_error(_http_error(404)) is IngestionErrorCategory.SOURCE_NOT_FOUND
    assert classify_ingestion_error(_http_error(500)) is IngestionErrorCategory.NETWORK
    assert classify_ingestion_error(_http_error(400)) is IngestionErrorCategory.INVALID_RESPONSE
