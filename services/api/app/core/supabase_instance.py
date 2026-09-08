from __future__ import annotations

import hashlib
from urllib.parse import urlparse


def supabase_instance_fingerprint(project_url: str | None) -> str:
    hostname = (urlparse(project_url or "").hostname or "").strip().lower()
    if not hostname:
        return ""
    return hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:16]
