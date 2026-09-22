from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine

import app.main as main_module
from app.core.rate_limit import RateLimitBucketRequest, consume_rate_limit


def test_rate_limit_counter_is_shared_in_postgres(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        bucket = RateLimitBucketRequest(
            scope="test-shared",
            key_hash="a" * 64,
            limit=2,
        )
        now = datetime(2026, 9, 21, 3, 0, 15, tzinfo=timezone.utc)

        first = consume_rate_limit(engine, bucket, window_seconds=60, now=now)
        second = consume_rate_limit(engine, bucket, window_seconds=60, now=now)
        third = consume_rate_limit(engine, bucket, window_seconds=60, now=now)

        assert first.allowed is True
        assert first.remaining == 1
        assert second.allowed is True
        assert second.remaining == 0
        assert third.allowed is False
        assert third.remaining == 0
    finally:
        engine.dispose()


def test_api_rate_limit_returns_429_and_isolated_by_remote_ip(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(main_module.settings, "rate_limit_network_requests", 100)
    monkeypatch.setattr(main_module.settings, "rate_limit_read_requests", 2)

    headers = {"X-Real-IP": "203.0.113.10"}
    first = client.get("/api/v1/me", headers=headers)
    second = client.get("/api/v1/me", headers=headers)
    limited = client.get("/api/v1/me", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.headers["retry-after"]
    assert limited.headers["ratelimit-remaining"] == "0"

    other_client = client.get(
        "/api/v1/me",
        headers={"X-Real-IP": "203.0.113.11"},
    )
    assert other_client.status_code == 200


def test_api_rate_limit_uses_alb_appended_client_ip_not_spoofed_prefix(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(main_module.settings, "rate_limit_network_requests", 100)
    monkeypatch.setattr(main_module.settings, "rate_limit_read_requests", 2)

    first = client.get(
        "/api/v1/me",
        headers={"X-Forwarded-For": "198.51.100.25, 203.0.113.20"},
    )
    second = client.get(
        "/api/v1/me",
        headers={"X-Forwarded-For": "192.0.2.99, 203.0.113.20"},
    )
    limited = client.get(
        "/api/v1/me",
        headers={"X-Forwarded-For": "198.51.100.77, 203.0.113.20"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"

    different_alb_client = client.get(
        "/api/v1/me",
        headers={"X-Forwarded-For": "198.51.100.25, 203.0.113.21"},
    )
    assert different_alb_client.status_code == 200


def test_railway_x_real_ip_takes_precedence_over_x_forwarded_for(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(main_module.settings, "rate_limit_network_requests", 100)
    monkeypatch.setattr(main_module.settings, "rate_limit_read_requests", 2)

    headers = {
        "X-Real-IP": "203.0.113.30",
        "X-Forwarded-For": "198.51.100.1, 203.0.113.31",
    }
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    assert client.get("/api/v1/me", headers=headers).status_code == 429

    assert client.get(
        "/api/v1/me",
        headers={
            "X-Real-IP": "203.0.113.31",
            "X-Forwarded-For": "198.51.100.1, 203.0.113.30",
        },
    ).status_code == 200


def test_health_and_readiness_are_not_rate_limited(client, monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(main_module.settings, "rate_limit_network_requests", 10)
    monkeypatch.setattr(main_module.settings, "rate_limit_read_requests", 10)

    for _ in range(12):
        response = client.get("/health", headers={"X-Real-IP": "203.0.113.12"})
        assert response.status_code == 200
        assert "ratelimit-limit" not in response.headers
