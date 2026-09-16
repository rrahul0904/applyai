from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.helpers import create_job


PROTOCOL_VERSION = "2026-07-28"
MCP_URL = "/api/v1/mcp"


def mcp_request(client, method: str, *, params=None, tool_name: str | None = None, request_id=1):
    headers = {
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if tool_name:
        headers["Mcp-Name"] = tool_name
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {
            **(params or {}),
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientInfo": {"name": "applyai-tests", "version": "1.0"},
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    return client.post(MCP_URL, json=payload, headers=headers)


def test_mcp_discovery_and_tools_are_modern_and_candidate_scoped(client):
    discover = mcp_request(client, "server/discover")
    assert discover.status_code == 200
    result = discover.json()["result"]
    assert result["supportedVersions"] == [PROTOCOL_VERSION]
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["cacheScope"] == "private"

    tools = mcp_request(client, "tools/list", request_id=2)
    assert tools.status_code == 200
    names = [tool["name"] for tool in tools.json()["result"]["tools"]]
    assert names == [
        "get_platform_context",
        "search_jobs",
        "browse_listings",
        "add_listing_to_pipeline",
        "apply_to_job",
    ]
    assert tools.json()["result"]["cacheScope"] == "private"


def test_mcp_rejects_routing_header_mismatch(client):
    response = client.post(
        MCP_URL,
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/list",
            "params": {
                "_meta": {"io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION}
            },
        },
        headers={
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "Mcp-Method": "server/discover",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32020


def test_mcp_can_search_and_idempotently_stage_listing(client, database_url):
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            job = create_job(session)
            job_id = str(job.id)
    finally:
        engine.dispose()

    search = mcp_request(
        client,
        "tools/call",
        tool_name="search_jobs",
        params={"name": "search_jobs", "arguments": {"query": "operations", "limit": 5}},
    )
    assert search.status_code == 200
    search_result = search.json()["result"]
    assert search_result["isError"] is False
    assert search_result["structuredContent"]["returned"] == 1
    assert search_result["structuredContent"]["listings"][0]["id"] == job_id

    first = mcp_request(
        client,
        "tools/call",
        tool_name="add_listing_to_pipeline",
        params={"name": "add_listing_to_pipeline", "arguments": {"job_id": job_id}},
        request_id=2,
    )
    assert first.status_code == 200
    first_data = first.json()["result"]["structuredContent"]
    assert first_data["created"] is True
    assert first_data["status"] == "PREPARING"
    assert first_data["submitted"] is False

    second = mcp_request(
        client,
        "tools/call",
        tool_name="add_listing_to_pipeline",
        params={"name": "add_listing_to_pipeline", "arguments": {"job_id": job_id}},
        request_id=3,
    )
    second_data = second.json()["result"]["structuredContent"]
    assert second_data["application_id"] == first_data["application_id"]
    assert second_data["created"] is False

    pipeline = client.get("/api/v1/applications")
    assert pipeline.status_code == 200
    assert pipeline.json()["returned"] == 1
    assert pipeline.json()["items"][0]["current_status"] == "PREPARING"


def test_apply_to_job_stops_at_existing_human_approval_boundary(client, database_url):
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            job = create_job(session)
            job_id = str(job.id)
    finally:
        engine.dispose()

    response = mcp_request(
        client,
        "tools/call",
        tool_name="apply_to_job",
        params={"name": "apply_to_job", "arguments": {"job_id": job_id}},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is False
    data = result["structuredContent"]
    assert data["status"] == "approval_required"
    assert data["pipeline_status"] == "PREPARING"
    assert data["submission_attempted"] is False

    pipeline = client.get("/api/v1/applications")
    assert pipeline.status_code == 200
    assert pipeline.json()["items"][0]["current_status"] == "PREPARING"


def test_mcp_never_exposes_cross_candidate_pipeline(client, switch_user, database_url):
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            job = create_job(session)
            job_id = str(job.id)
    finally:
        engine.dispose()

    staged = mcp_request(
        client,
        "tools/call",
        tool_name="add_listing_to_pipeline",
        params={"name": "add_listing_to_pipeline", "arguments": {"job_id": job_id}},
    )
    assert staged.status_code == 200

    switch_user("clerk_user_b", "b@example.com")
    context = mcp_request(
        client,
        "tools/call",
        tool_name="get_platform_context",
        params={"name": "get_platform_context", "arguments": {}},
        request_id=2,
    )
    assert context.status_code == 200
    assert context.json()["result"]["structuredContent"]["pipeline"]["total"] == 0
