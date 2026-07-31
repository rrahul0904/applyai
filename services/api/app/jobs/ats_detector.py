from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app.jobs.contracts import JobSourceType


@dataclass(frozen=True)
class ATSDetection:
    provider: JobSourceType
    confidence: float
    evidence: tuple[str, ...]
    candidate_source_url: str
    source_identity: str


class _ReferenceParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.references: list[str] = []
        self.meta_values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"a", "link"} and values.get("href"):
            self.references.append(urljoin(self.base_url, str(values["href"])))
        if tag in {"script", "iframe", "img"} and values.get("src"):
            self.references.append(urljoin(self.base_url, str(values["src"])))
        if tag == "meta" and values.get("content"):
            self.meta_values.append(str(values["content"]))


_PROVIDER_PATTERNS: list[tuple[JobSourceType, tuple[str, ...]]] = [
    (JobSourceType.GREENHOUSE, ("boards.greenhouse.io", "job-boards.greenhouse.io", "boards-api.greenhouse.io")),
    (JobSourceType.LEVER, ("jobs.lever.co", "api.lever.co", "api.eu.lever.co")),
    (JobSourceType.ASHBY, ("jobs.ashbyhq.com", "api.ashbyhq.com/posting-api")),
    (JobSourceType.WORKDAY, ("myworkdayjobs.com", "wd1.myworkdaysite.com", "wd5.myworkdaysite.com")),
    (JobSourceType.SMARTRECRUITERS, ("careers.smartrecruiters.com", "jobs.smartrecruiters.com")),
    (JobSourceType.WORKABLE, ("apply.workable.com", "workable.com/j/")),
    (JobSourceType.ICIMS, ("icims.com/jobs", "careers-", "jobs.icims.com")),
    (JobSourceType.ORACLE, ("oraclecloud.com/hcmui", "oracle.com/careers")),
    (JobSourceType.SUCCESSFACTORS, ("successfactors.com", "career5.successfactors.eu")),
]

_EXTRA_PROVIDER_NAMES = {
    "jobvite": "JOBVITE",
    "recruiting.ultipro.com": "UKG",
    "ukg.com/careers": "UKG",
}


def _source_identity(provider: JobSourceType, url: str) -> str:
    parsed = urlsplit(url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    host = parsed.hostname.casefold() if parsed.hostname else ""
    if provider == JobSourceType.GREENHOUSE:
        for marker in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
            if marker in host and segments:
                return segments[0]
    if provider == JobSourceType.LEVER and "lever.co" in host and segments:
        return segments[0]
    if provider == JobSourceType.ASHBY and "ashbyhq.com" in host and segments:
        if segments[0] == "posting-api" and len(segments) >= 3:
            return segments[2]
        return segments[0]
    if provider == JobSourceType.WORKDAY:
        return f"{host}:{segments[0] if segments else 'root'}"
    if provider in {JobSourceType.SMARTRECRUITERS, JobSourceType.WORKABLE} and segments:
        return segments[0]
    return host or url


def detect_ats(url: str, html: str = "") -> ATSDetection:
    parser = _ReferenceParser(url)
    parser.feed(html[:2_000_000])
    candidates = [url, *parser.references, *parser.meta_values]
    normalized = [candidate.casefold() for candidate in candidates]

    matches: dict[JobSourceType, list[str]] = {}
    match_urls: dict[JobSourceType, str] = {}
    for provider, patterns in _PROVIDER_PATTERNS:
        for original, value in zip(candidates, normalized, strict=False):
            for pattern in patterns:
                if pattern in value:
                    matches.setdefault(provider, []).append(f"matched:{pattern}")
                    match_urls.setdefault(provider, original)

    if matches:
        provider = max(matches, key=lambda item: len(set(matches[item])))
        evidence = tuple(sorted(set(matches[provider])))
        source_url = match_urls[provider]
        exact_host = any(
            pattern in (urlsplit(url).hostname or "").casefold()
            for candidate_provider, patterns in _PROVIDER_PATTERNS
            if candidate_provider == provider
            for pattern in patterns
        )
        confidence = 1.0 if exact_host else min(0.98, 0.82 + 0.04 * len(evidence))
        return ATSDetection(
            provider=provider,
            confidence=confidence,
            evidence=evidence,
            candidate_source_url=source_url,
            source_identity=_source_identity(provider, source_url),
        )

    joined = "\n".join(normalized)
    for signal, name in _EXTRA_PROVIDER_NAMES.items():
        if signal in joined:
            # These providers are detected for operational evidence but remain a
            # conservative custom-career source until a dedicated adapter exists.
            return ATSDetection(
                provider=JobSourceType.CAREER_SITE,
                confidence=0.75,
                evidence=(f"provider-signal:{name}",),
                candidate_source_url=url,
                source_identity=(urlsplit(url).hostname or url).casefold(),
            )

    if re.search(r"\b(job|career|position|opening)s?\b", html.casefold()):
        return ATSDetection(
            provider=JobSourceType.CAREER_SITE,
            confidence=0.55,
            evidence=("career-content-signal",),
            candidate_source_url=url,
            source_identity=(urlsplit(url).hostname or url).casefold(),
        )
    return ATSDetection(
        provider=JobSourceType.CAREER_SITE,
        confidence=0.25,
        evidence=("no-known-ats-fingerprint",),
        candidate_source_url=url,
        source_identity=(urlsplit(url).hostname or url).casefold(),
    )
