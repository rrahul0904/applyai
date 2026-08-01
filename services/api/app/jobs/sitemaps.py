from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

from app.jobs.web_security import CrawlBudgetExceeded, SafeHttpFetcher, validate_public_http_url


_JOB_PATH = re.compile(r"/(?:jobs?|careers?|positions?|openings?)(?:/|$)", re.IGNORECASE)


@dataclass(frozen=True)
class SitemapDiscoveryResult:
    sitemap_urls: tuple[str, ...]
    candidate_job_urls: tuple[str, ...]


def _root_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))


def sitemap_urls_from_robots(robots_text: str, base_url: str) -> list[str]:
    results: list[str] = []
    for line in robots_text.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().casefold() == "sitemap":
            candidate = urljoin(base_url, value.strip())
            if candidate not in results:
                results.append(candidate)
    return results


def _parse_locs(xml_text: str) -> tuple[str, list[str]]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ValueError("Sitemap XML is malformed") from exc
    tag = root.tag.rsplit("}", 1)[-1].casefold()
    locations: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].casefold() == "loc" and element.text:
            locations.append(element.text.strip())
    return tag, locations


def discover_job_urls_from_sitemaps(
    fetcher: SafeHttpFetcher,
    base_url: str,
    *,
    robots_text: str | None = None,
    max_sitemaps: int = 4,
    max_job_urls: int = 500,
) -> SitemapDiscoveryResult:
    root = _root_url(base_url)
    candidates = sitemap_urls_from_robots(robots_text or "", root)
    for default in ("sitemap.xml", "sitemap_index.xml", "jobs-sitemap.xml"):
        value = urljoin(root, default)
        if value not in candidates:
            candidates.append(value)

    visited: list[str] = []
    job_urls: list[str] = []
    queue = candidates[:max_sitemaps]
    while queue and len(visited) < max_sitemaps:
        sitemap_url = queue.pop(0)
        if sitemap_url in visited:
            continue
        try:
            sitemap_url = validate_public_http_url(sitemap_url, resolver=fetcher.resolver)
            result = fetcher.fetch(sitemap_url, accept="application/xml,text/xml,*/*;q=0.1")
        except (ValueError, CrawlBudgetExceeded):
            continue
        if result.status_code >= 400:
            continue
        try:
            root_tag, locations = _parse_locs(result.text)
        except ValueError:
            continue
        visited.append(result.final_url)
        if root_tag == "sitemapindex":
            for location in locations:
                if len(visited) + len(queue) >= max_sitemaps:
                    break
                if location not in visited and location not in queue:
                    queue.append(location)
            continue
        for location in locations:
            if len(job_urls) >= max_job_urls:
                break
            try:
                canonical = validate_public_http_url(location, resolver=fetcher.resolver)
            except ValueError:
                continue
            if _JOB_PATH.search(urlsplit(canonical).path) and canonical not in job_urls:
                job_urls.append(canonical)

    return SitemapDiscoveryResult(tuple(visited), tuple(job_urls))
