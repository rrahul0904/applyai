from __future__ import annotations

import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


class PublicUrlRejected(ValueError):
    pass


class CrawlBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class CrawlBudget:
    max_pages: int = 8
    max_response_bytes: int = 2 * 1024 * 1024
    max_redirects: int = 4
    request_timeout_seconds: float = 12.0


@dataclass(frozen=True)
class SafeFetchResult:
    requested_url: str
    final_url: str
    status_code: int
    content: bytes
    content_type: str | None
    etag: str | None
    last_modified: str | None

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def text(self) -> str:
        content_type = self.content_type or ""
        charset = "utf-8"
        for part in content_type.split(";")[1:]:
            key, _, value = part.strip().partition("=")
            if key.casefold() == "charset" and value:
                charset = value.strip('"')
                break
        try:
            return self.content.decode(charset, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


Resolver = Callable[[str, int], Iterable[tuple]]


def _default_resolver(host: str, port: int) -> Iterable[tuple]:
    return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)


def _is_forbidden_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return not ip.is_global


def validate_public_http_url(
    value: str,
    *,
    resolver: Resolver = _default_resolver,
) -> str:
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"}:
        raise PublicUrlRejected("Only public HTTP/HTTPS URLs are supported")
    if not parsed.hostname:
        raise PublicUrlRejected("URL hostname is required")
    if parsed.username or parsed.password:
        raise PublicUrlRejected("Credential-bearing URLs are not supported")
    host = parsed.hostname.rstrip(".").casefold()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise PublicUrlRejected("Localhost destinations are blocked")
    if host.endswith(".local") or host.endswith(".internal"):
        raise PublicUrlRejected("Private DNS suffixes are blocked")

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise PublicUrlRejected("URL port is invalid") from exc

    # Literal IPs are validated directly. DNS names must resolve and every returned
    # address must be globally routable; a mixed public/private answer is rejected.
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise PublicUrlRejected("Private, loopback, link-local and reserved IPs are blocked")
    else:
        try:
            results = list(resolver(host, port))
        except OSError as exc:
            raise PublicUrlRejected("Hostname could not be resolved") from exc
        addresses = {
            result[4][0]
            for result in results
            if len(result) >= 5 and result[4]
        }
        if not addresses:
            raise PublicUrlRejected("Hostname did not resolve to an address")
        if any(_is_forbidden_address(address) for address in addresses):
            raise PublicUrlRejected("Hostname resolves to a non-public address")

    netloc = host
    if parsed.port and not ((scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443)):
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


class SafeHttpFetcher:
    """Bounded public HTTP client with per-hop SSRF checks and no JS execution."""

    def __init__(
        self,
        *,
        budget: CrawlBudget | None = None,
        client: httpx.Client | None = None,
        resolver: Resolver = _default_resolver,
        user_agent: str = "ApplyAI-JobDiscovery/1.0",
    ) -> None:
        self.budget = budget or CrawlBudget()
        self.resolver = resolver
        self._owns_client = client is None
        self.client = client or httpx.Client(
            follow_redirects=False,
            timeout=self.budget.request_timeout_seconds,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )
        self.pages_fetched = 0

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def fetch(
        self,
        url: str,
        *,
        accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8",
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> SafeFetchResult:
        if self.pages_fetched >= self.budget.max_pages:
            raise CrawlBudgetExceeded("Per-source page budget was exhausted")
        requested = validate_public_http_url(url, resolver=self.resolver)
        current = requested
        headers = {"Accept": accept}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        for redirect_count in range(self.budget.max_redirects + 1):
            current = validate_public_http_url(current, resolver=self.resolver)
            self.pages_fetched += 1
            with self.client.stream("GET", current, headers=headers) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirect_count >= self.budget.max_redirects:
                        raise CrawlBudgetExceeded("Redirect budget was exhausted")
                    location = response.headers.get("Location")
                    if not location:
                        raise PublicUrlRejected("Redirect response omitted Location")
                    current = urljoin(current, location)
                    continue

                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > self.budget.max_response_bytes:
                        raise CrawlBudgetExceeded("Response exceeded the decompressed byte budget")
                return SafeFetchResult(
                    requested_url=requested,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content=bytes(content),
                    content_type=response.headers.get("Content-Type"),
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                )
        raise CrawlBudgetExceeded("Redirect budget was exhausted")
