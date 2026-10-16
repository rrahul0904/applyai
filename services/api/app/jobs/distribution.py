from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx


SUPPORTED_CHANNELS = {"REDDIT", "TELEGRAM", "NEWSLETTER", "LINKEDIN", "BLUESKY"}


@dataclass(frozen=True)
class DistributionMessage:
    title: str
    text: str
    url: str
    target: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DistributionReceipt:
    status: str
    channel: str
    external_id: str | None = None
    external_url: str | None = None
    detail: str | None = None
    raw: dict[str, Any] | None = None


class DistributionError(RuntimeError):
    pass


class DistributionPublisher:
    """Governed external publisher.

    Live network writes are disabled unless APPLYAI_EXTERNAL_PUBLISHING_ENABLED=true.
    Credentials are read only at execution time. Callers must enforce their own approval
    state before invoking publish; this class adds a second write gate intentionally.
    """

    def __init__(self, *, client: httpx.Client | None = None, timeout_seconds: float = 20.0) -> None:
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    @staticmethod
    def live_enabled() -> bool:
        return os.getenv("APPLYAI_EXTERNAL_PUBLISHING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}

    def publish(self, channel: str, message: DistributionMessage, *, dry_run: bool) -> DistributionReceipt:
        channel = channel.upper()
        if channel not in SUPPORTED_CHANNELS:
            raise DistributionError(f"Unsupported distribution channel: {channel}")
        if dry_run:
            return DistributionReceipt(
                status="DRY_RUN",
                channel=channel,
                detail="Validated publication without external write",
                raw={"title": message.title, "text": message.text, "url": message.url, "target": message.target},
            )
        if not self.live_enabled():
            raise DistributionError("External publishing is disabled by APPLYAI_EXTERNAL_PUBLISHING_ENABLED")
        method = getattr(self, f"_publish_{channel.lower()}")
        return method(message)

    def _publish_telegram(self, message: DistributionMessage) -> DistributionReceipt:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise DistributionError("TELEGRAM_BOT_TOKEN is required")
        response = self.client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": message.target,
                "text": f"{message.title}\n\n{message.text}\n\n{message.url}"[:4096],
                "disable_web_page_preview": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        message_id = str(result.get("message_id")) if isinstance(result, dict) and result.get("message_id") is not None else None
        return DistributionReceipt(status="PUBLISHED", channel="TELEGRAM", external_id=message_id, raw=payload)

    def _publish_reddit(self, message: DistributionMessage) -> DistributionReceipt:
        token = os.getenv("REDDIT_ACCESS_TOKEN", "").strip()
        user_agent = os.getenv("REDDIT_USER_AGENT", "ApplyAI/1.0").strip()
        if not token:
            raise DistributionError("REDDIT_ACCESS_TOKEN is required")
        subreddit = message.target.removeprefix("r/").strip("/")
        response = self.client.post(
            "https://oauth.reddit.com/api/submit",
            headers={"Authorization": f"Bearer {token}", "User-Agent": user_agent},
            data={
                "api_type": "json",
                "kind": "link",
                "sr": subreddit,
                "title": message.title[:300],
                "url": message.url,
                "resubmit": "true",
                "sendreplies": "false",
            },
        )
        response.raise_for_status()
        payload = response.json()
        errors = (((payload or {}).get("json") or {}).get("errors") or []) if isinstance(payload, dict) else []
        if errors:
            raise DistributionError(f"Reddit rejected publication: {errors}")
        data = (((payload or {}).get("json") or {}).get("data") or {}) if isinstance(payload, dict) else {}
        external_url = data.get("url") if isinstance(data, dict) else None
        external_id = data.get("id") if isinstance(data, dict) else None
        return DistributionReceipt(status="PUBLISHED", channel="REDDIT", external_id=external_id, external_url=external_url, raw=payload)

    def _publish_linkedin(self, message: DistributionMessage) -> DistributionReceipt:
        token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
        author = message.target or os.getenv("LINKEDIN_AUTHOR_URN", "").strip()
        if not token or not author:
            raise DistributionError("LINKEDIN_ACCESS_TOKEN and an author URN target are required")
        commentary = f"{message.title}\n\n{message.text}\n\n{message.url}"[:3000]
        response = self.client.post(
            "https://api.linkedin.com/rest/posts",
            headers={
                "Authorization": f"Bearer {token}",
                "LinkedIn-Version": os.getenv("LINKEDIN_API_VERSION", "202609"),
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            json={
                "author": author,
                "commentary": commentary,
                "visibility": "PUBLIC",
                "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
        )
        response.raise_for_status()
        external_id = response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id")
        raw = response.json() if response.content else {}
        return DistributionReceipt(status="PUBLISHED", channel="LINKEDIN", external_id=external_id, raw=raw)

    def _publish_bluesky(self, message: DistributionMessage) -> DistributionReceipt:
        handle = os.getenv("BLUESKY_HANDLE", "").strip()
        password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
        service = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social").rstrip("/")
        if not handle or not password:
            raise DistributionError("BLUESKY_HANDLE and BLUESKY_APP_PASSWORD are required")
        session_response = self.client.post(
            f"{service}/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
        )
        session_response.raise_for_status()
        auth = session_response.json()
        access_jwt = auth.get("accessJwt")
        did = auth.get("did")
        if not access_jwt or not did:
            raise DistributionError("Bluesky session did not return accessJwt and did")
        text = f"{message.title}\n\n{message.text}\n\n{message.url}"[:300]
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        response = self.client.post(
            f"{service}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {access_jwt}"},
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {"$type": "app.bsky.feed.post", "text": text, "createdAt": created_at},
            },
        )
        response.raise_for_status()
        payload = response.json()
        return DistributionReceipt(
            status="PUBLISHED",
            channel="BLUESKY",
            external_id=payload.get("cid"),
            external_url=payload.get("uri"),
            raw=payload,
        )

    def _publish_newsletter(self, message: DistributionMessage) -> DistributionReceipt:
        webhook = os.getenv("NEWSLETTER_PUBLISH_WEBHOOK_URL", "").strip()
        token = os.getenv("NEWSLETTER_PUBLISH_TOKEN", "").strip()
        if not webhook:
            raise DistributionError("NEWSLETTER_PUBLISH_WEBHOOK_URL is required")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.post(
            webhook,
            headers=headers,
            json={
                "target": message.target,
                "title": message.title,
                "text": message.text,
                "url": message.url,
                "metadata": message.metadata,
            },
        )
        response.raise_for_status()
        payload = response.json() if response.content else {}
        return DistributionReceipt(
            status="PUBLISHED",
            channel="NEWSLETTER",
            external_id=str(payload.get("id")) if isinstance(payload, dict) and payload.get("id") is not None else None,
            external_url=payload.get("url") if isinstance(payload, dict) else None,
            raw=payload if isinstance(payload, dict) else {},
        )
