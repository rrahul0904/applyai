from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hmac import compare_digest

from sqlalchemy import text
from sqlalchemy.engine import Engine
from starlette.requests import Request

from app.core.config import Settings


@dataclass(frozen=True)
class RateLimitBucketRequest:
    scope: str
    key_hash: str
    limit: int


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    scope: str


_EXEMPT_PATHS = {
    "/health",
    "/ready",
    "/api/docs",
    "/api/v1/openapi.json",
}
_CLEANUP_INTERVAL_SECONDS = 300.0
_cleanup_lock = threading.Lock()
_last_cleanup_at = 0.0


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _remote_ip(request: Request) -> str:
    # Railway's public proxy injects X-Real-IP with the remote client address.
    # Fall back to the ASGI peer for local/dev runners and other deployments.
    forwarded = request.headers.get("x-real-ip", "").strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client is not None else "unknown"


def _valid_internal_token(request: Request, settings: Settings) -> bool:
    expected = settings.internal_api_token
    supplied = request.headers.get("x-applyai-internal-token", "")
    return bool(expected and supplied and compare_digest(supplied, expected))


def _request_class(request: Request) -> str:
    path = request.url.path
    if path == "/api/v1/billing/webhook":
        return "provider-webhook"
    if request.method in {"GET", "HEAD"}:
        return "read"
    lowered = path.lower()
    if "resume" in lowered and ("upload" in lowered or "import" in lowered):
        return "upload"
    if any(
        fragment in lowered
        for fragment in (
            "/agents",
            "/application-agent",
            "/career-v2/",
            "/interview",
            "/job-import",
            "/job-discover",
        )
    ):
        return "expensive"
    return "write"


def request_rate_limit_buckets(
    request: Request,
    settings: Settings,
) -> list[RateLimitBucketRequest]:
    if not settings.rate_limit_runtime_enabled:
        return []
    if request.method == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
        return []
    if not request.url.path.startswith("/api/"):
        return []
    if request.url.path.startswith("/api/v1/internal/") and _valid_internal_token(request, settings):
        return []

    ip_hash = _hash_key(f"ip:{_remote_ip(request)}")
    request_class = _request_class(request)
    class_limit = {
        "read": settings.rate_limit_read_requests,
        "write": settings.rate_limit_write_requests,
        "expensive": settings.rate_limit_expensive_requests,
        "upload": settings.rate_limit_upload_requests,
        "provider-webhook": settings.rate_limit_webhook_requests,
    }[request_class]

    buckets = [
        RateLimitBucketRequest(
            scope="network",
            key_hash=ip_hash,
            limit=settings.rate_limit_network_requests,
        ),
        RateLimitBucketRequest(
            scope=request_class,
            key_hash=ip_hash,
            limit=class_limit,
        ),
    ]

    authorization = request.headers.get("authorization", "").strip()
    if authorization.lower().startswith("bearer ") and len(authorization) > 16:
        credential_hash = _hash_key(f"credential:{authorization}")
        buckets.append(
            RateLimitBucketRequest(
                scope=f"{request_class}:credential",
                key_hash=credential_hash,
                limit=class_limit,
            )
        )
    return buckets


def _window_start(now: datetime, window_seconds: int) -> datetime:
    epoch_seconds = int(now.timestamp())
    start = epoch_seconds - (epoch_seconds % window_seconds)
    return datetime.fromtimestamp(start, tz=timezone.utc)


def _maybe_cleanup(engine: Engine, now: datetime) -> None:
    global _last_cleanup_at
    monotonic_now = time.monotonic()
    if monotonic_now - _last_cleanup_at < _CLEANUP_INTERVAL_SECONDS:
        return
    with _cleanup_lock:
        if monotonic_now - _last_cleanup_at < _CLEANUP_INTERVAL_SECONDS:
            return
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM api_rate_limit_buckets WHERE expires_at < :now"),
                {"now": now},
            )
        _last_cleanup_at = monotonic_now


def consume_rate_limit(
    engine: Engine,
    bucket: RateLimitBucketRequest,
    *,
    window_seconds: int,
    now: datetime | None = None,
) -> RateLimitDecision:
    instant = now or datetime.now(timezone.utc)
    window_start = _window_start(instant, window_seconds)
    reset_at = window_start + timedelta(seconds=window_seconds)
    expires_at = reset_at + timedelta(seconds=window_seconds)

    with engine.begin() as connection:
        count = int(
            connection.scalar(
                text(
                    """
                    INSERT INTO api_rate_limit_buckets
                        (scope, key_hash, window_start, request_count, expires_at)
                    VALUES
                        (:scope, :key_hash, :window_start, 1, :expires_at)
                    ON CONFLICT (scope, key_hash, window_start)
                    DO UPDATE SET
                        request_count = api_rate_limit_buckets.request_count + 1,
                        expires_at = EXCLUDED.expires_at
                    RETURNING request_count
                    """
                ),
                {
                    "scope": bucket.scope,
                    "key_hash": bucket.key_hash,
                    "window_start": window_start,
                    "expires_at": expires_at,
                },
            )
            or 0
        )

    _maybe_cleanup(engine, instant)
    reset_seconds = max(1, math.ceil((reset_at - instant).total_seconds()))
    return RateLimitDecision(
        allowed=count <= bucket.limit,
        limit=bucket.limit,
        remaining=max(0, bucket.limit - count),
        reset_seconds=reset_seconds,
        scope=bucket.scope,
    )


def enforce_rate_limit(
    engine: Engine,
    buckets: list[RateLimitBucketRequest],
    *,
    window_seconds: int,
) -> RateLimitDecision | None:
    tightest: RateLimitDecision | None = None
    for bucket in buckets:
        decision = consume_rate_limit(
            engine,
            bucket,
            window_seconds=window_seconds,
        )
        if tightest is None or decision.remaining < tightest.remaining:
            tightest = decision
        if not decision.allowed:
            return decision
    return tightest
