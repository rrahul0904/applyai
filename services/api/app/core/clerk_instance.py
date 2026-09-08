from __future__ import annotations

import hashlib
from urllib.parse import urlparse


def clerk_instance_fingerprint(issuer: str | None) -> str:
    hostname = (urlparse(issuer or "").hostname or "").strip().lower()
    if not hostname:
        return ""
    return hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:16]
