from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app.jobs.adapters import normalized_from_raw
from app.jobs.career_extractor import extract_career_page
from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.contracts import RawJobPosting, canonicalize_public_url
from app.jobs.robots import AccessPolicy, evaluate_robots
from app.jobs.sitemaps import discover_job_urls_from_sitemaps
from app.jobs.web_security import CrawlBudget, PublicUrlRejected, SafeHttpFetcher


class _JobLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        href = values.get("href")
        if not href:
            return
        candidate = canonicalize_public_url(urljoin(self.base_url, str(href)))
        if not candidate:
            return
        path = urlsplit(candidate).path.casefold()
        if any(token in path for token in ("/job/", "/jobs/", "/position/", "/positions/", "/opening/")):
            if candidate not in self.links:
                self.links.append(candidate)


class CareerSiteJobConnector(JobSourceConnector):
    """Conservative recurring connector for public employer career sites.

    It uses only bounded HTTP, robots policy, sitemaps and job-like links. It does not
    execute JavaScript or bypass access controls. Because arbitrary career sites cannot
    guarantee a complete listing snapshot, absence from a run is never closure evidence;
    URL verification handles closure separately.
    """

    key = "career-site"
    authoritative_snapshot = False

    def __init__(
        self,
        careers_url: str,
        *,
        source_identity: str,
        max_pages: int = 60,
        max_jobs: int = 50,
        max_response_bytes: int = 2 * 1024 * 1024,
        max_redirects: int = 4,
        timeout_seconds: float = 12.0,
        fetcher: SafeHttpFetcher | None = None,
    ) -> None:
        self.careers_url = careers_url
        self._source_identity = source_identity
        self.max_jobs = max(1, min(int(max_jobs), 500))
        self._owns_fetcher = fetcher is None
        self.fetcher = fetcher or SafeHttpFetcher(
            budget=CrawlBudget(
                max_pages=max(6, min(int(max_pages), 1000)),
                max_response_bytes=max_response_bytes,
                max_redirects=max_redirects,
                request_timeout_seconds=timeout_seconds,
            ),
            user_agent="ApplyAI-JobIngestion/1.0",
        )
        self._last_fetch_at: datetime | None = None
        self._last_count = 0
        self._access_policy = AccessPolicy.UNKNOWN

    def source_company_identity(self) -> str:
        return self._source_identity

    def close(self) -> None:
        if self._owns_fetcher:
            self.fetcher.close()

    def fetch(self, checkpoint):
        del checkpoint
        robots = evaluate_robots(self.fetcher, self.careers_url, user_agent="ApplyAI-JobIngestion")
        self._access_policy = robots.policy
        if robots.policy == AccessPolicy.DISALLOWED:
            raise PublicUrlRejected("robots policy disallows employer career source")
        if robots.policy == AccessPolicy.MANUAL_REVIEW:
            raise PublicUrlRejected("employer career source requires manual access-policy review")

        listing = self.fetcher.fetch(self.careers_url)
        if listing.status_code >= 400:
            raise RuntimeError(f"Employer career source returned HTTP {listing.status_code}")

        candidate_urls: list[str] = []
        parser = _JobLinkParser(listing.final_url)
        parser.feed(listing.text[:2_000_000])
        listing_host = urlsplit(listing.final_url).hostname
        for url in parser.links:
            if urlsplit(url).hostname == listing_host and url not in candidate_urls:
                candidate_urls.append(url)

        try:
            sitemap_result = discover_job_urls_from_sitemaps(
                self.fetcher,
                listing.final_url,
                max_sitemaps=min(6, max(1, self.fetcher.budget.max_pages // 5)),
                max_job_urls=max(self.max_jobs * 4, self.max_jobs),
            )
            for url in sitemap_result.candidate_job_urls:
                if urlsplit(url).hostname == listing_host and url not in candidate_urls:
                    candidate_urls.append(url)
        except Exception:
            # Sitemap discovery is additive. A valid listing page can still supply jobs.
            pass

        records: list[dict] = []
        for url in candidate_urls[: self.max_jobs]:
            if self.fetcher.pages_fetched >= self.fetcher.budget.max_pages:
                break
            try:
                result = self.fetcher.fetch(url)
            except Exception:
                continue
            if result.status_code >= 400:
                continue
            extraction = extract_career_page(result.text, page_url=result.final_url)
            if extraction.posting is None:
                continue
            records.append(
                {
                    "_applyai_page_url": result.final_url,
                    "_applyai_page_html": result.text,
                    "_applyai_fetched_at": datetime.now(timezone.utc).isoformat(),
                    "_applyai_extraction_confidence": extraction.confidence,
                    "_applyai_extraction_evidence": list(extraction.evidence),
                }
            )

        # Some small employer sites expose one job directly at the configured URL.
        if not records:
            extraction = extract_career_page(listing.text, page_url=listing.final_url)
            if extraction.posting is not None:
                records.append(
                    {
                        "_applyai_page_url": listing.final_url,
                        "_applyai_page_html": listing.text,
                        "_applyai_fetched_at": datetime.now(timezone.utc).isoformat(),
                        "_applyai_extraction_confidence": extraction.confidence,
                        "_applyai_extraction_evidence": list(extraction.evidence),
                    }
                )

        self._last_fetch_at = datetime.now(timezone.utc)
        self._last_count = len(records)
        return records

    def to_raw(self, payload: dict) -> RawJobPosting:
        page_url = str(payload.get("_applyai_page_url") or "")
        html = str(payload.get("_applyai_page_html") or "")
        extraction = extract_career_page(html, page_url=page_url)
        if extraction.posting is None:
            raise ValueError("Career page no longer produces a valid single-job posting")
        posting = extraction.posting
        metadata = dict(posting.source_metadata or {})
        metadata.update(
            {
                "career_source_identity": self._source_identity,
                "extraction_confidence": extraction.confidence,
                "extraction_evidence": list(extraction.evidence),
                "access_policy": self._access_policy.value,
            }
        )
        return RawJobPosting(
            **{
                **posting.__dict__,
                "source_company_identity": self._source_identity,
                "source_metadata": metadata,
            }
        )

    def normalize(self, payload: dict) -> NormalizedJob:
        return normalized_from_raw(self.to_raw(payload))

    def checkpoint(self) -> dict:
        return {
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "count": self._last_count,
            "authoritative_snapshot": False,
            "access_policy": self._access_policy.value,
        }

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            True,
            datetime.now(timezone.utc),
            "Career-site connector configured; robots/access policy is enforced during fetch",
        )
