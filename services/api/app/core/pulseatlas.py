from __future__ import annotations

import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

_PROJECT = {"organizationId": "portfolio_primary", "projectId": "proj_applyai", "projectSlug": "applyai"}
_APPLICATION_STATUS = re.compile(r"^/api/v1/applications/[0-9a-fA-F-]+/status$")


def _environment() -> str:
    value = os.getenv("PULSEATLAS_ENVIRONMENT", "production")
    return value if value in {"development", "preview", "production"} else "production"


def event_for_request(method: str, path: str, status_code: int) -> tuple[str, str, dict[str, Any]] | None:
    if status_code >= 400:
        return None
    method = method.upper()
    if method == "GET" and path == "/health":
        return ("health_check", "health", {"component": "applyai-api", "status": "ok"})
    if method == "POST" and path.rstrip("/") == "/api/v1/applications":
        return ("application_created", "product", {})
    if method == "PATCH" and _APPLICATION_STATUS.fullmatch(path):
        return ("application_status_changed", "product", {})
    return None


def _post(event: tuple[str, str, dict[str, Any]]) -> None:
    endpoint = os.getenv("PULSEATLAS_ENDPOINT", "").strip()
    write_key = os.getenv("PULSEATLAS_WRITE_KEY", "").strip()
    if not endpoint or not write_key:
        return
    try:
        url = httpx.URL(endpoint)
        if url.scheme != "https" and url.host not in {"localhost", "127.0.0.1"}:
            return
        name, category, properties = event
        httpx.post(endpoint, headers={"content-type": "application/json", "x-pulseatlas-write-key": write_key}, json={
            "id": f"evt_{uuid.uuid4()}", "schemaVersion": 1, **_PROJECT, "environment": _environment(),
            "eventName": name, "eventCategory": category, "occurredAt": datetime.now(timezone.utc).isoformat(), "properties": properties,
        }, timeout=1.5)
    except Exception:
        return


def dispatch_request_event(method: str, path: str, status_code: int) -> None:
    event = event_for_request(method, path, status_code)
    if event:
        threading.Thread(target=_post, args=(event,), daemon=True, name="pulseatlas-sink").start()
