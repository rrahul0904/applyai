from __future__ import annotations

import json

import httpx
import pytest

from app.jobs.distribution import (
    DistributionError,
    DistributionMessage,
    DistributionPublisher,
)


def message(target: str = "jobs") -> DistributionMessage:
    return DistributionMessage(
        title="Senior Data Engineer",
        text="Build trustworthy data systems.",
        url="https://jobs.example.com/123",
        target=target,
        metadata={"job_id": "123"},
    )


def test_dry_run_never_performs_network_write() -> None:
    def fail_if_called(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("dry-run attempted a network request")

    client = httpx.Client(transport=httpx.MockTransport(fail_if_called))
    publisher = DistributionPublisher(client=client)
    receipt = publisher.publish("TELEGRAM", message("-1001"), dry_run=True)

    assert receipt.status == "DRY_RUN"
    assert receipt.channel == "TELEGRAM"
    assert receipt.raw == {
        "title": "Senior Data Engineer",
        "text": "Build trustworthy data systems.",
        "url": "https://jobs.example.com/123",
        "target": "-1001",
    }


def test_live_publish_requires_global_write_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPLYAI_EXTERNAL_PUBLISHING_ENABLED", raising=False)
    publisher = DistributionPublisher(client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))

    with pytest.raises(DistributionError, match="External publishing is disabled"):
        publisher.publish("TELEGRAM", message("-1001"), dry_run=False)


def test_telegram_publish_uses_configured_bot_and_target(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    monkeypatch.setenv("APPLYAI_EXTERNAL_PUBLISHING_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    publisher = DistributionPublisher(client=client)

    receipt = publisher.publish("TELEGRAM", message("-100123"), dry_run=False)

    assert receipt.status == "PUBLISHED"
    assert receipt.external_id == "42"
    assert len(requests) == 1
    assert requests[0].url.path == "/bottest-token/sendMessage"
    body = json.loads(requests[0].content)
    assert body["chat_id"] == "-100123"
    assert "https://jobs.example.com/123" in body["text"]


def test_unsupported_channel_is_rejected_before_network() -> None:
    publisher = DistributionPublisher(client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))
    with pytest.raises(DistributionError, match="Unsupported distribution channel"):
        publisher.publish("UNKNOWN", message(), dry_run=True)
