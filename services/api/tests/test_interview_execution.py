from __future__ import annotations


def test_interview_execution_is_fail_closed_without_remote_sandbox(client, monkeypatch) -> None:
    monkeypatch.delenv("INTERVIEW_EXECUTION_PROVIDER", raising=False)
    monkeypatch.delenv("INTERVIEW_PISTON_URL", raising=False)
    assert client.get("/api/v1/me").status_code == 200

    capability = client.get("/api/v1/interview-intelligence/execution/capability")
    assert capability.status_code == 200, capability.text
    payload = capability.json()
    assert payload["configured"] is False
    assert payload["provider"] == "disabled"
    assert payload["sql_execution"] is False
    assert payload["trust_boundary"] == "remote-isolated-sandbox"

    execution = client.post(
        "/api/v1/interview-intelligence/execution/run",
        json={"language": "python", "code": "print('safe boundary')", "stdin": ""},
    )
    assert execution.status_code == 503
