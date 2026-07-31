from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from app.jobs.web_security import SafeHttpFetcher


class AccessPolicy(StrEnum):
    ALLOWED = "ALLOWED"
    DISALLOWED = "DISALLOWED"
    UNKNOWN = "UNKNOWN"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True)
class RobotsDecision:
    policy: AccessPolicy
    robots_url: str
    detail: str


def robots_url_for(target_url: str) -> str:
    parsed = urlsplit(target_url)
    return urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))


def evaluate_robots(
    fetcher: SafeHttpFetcher,
    target_url: str,
    *,
    user_agent: str = "ApplyAI-JobDiscovery",
) -> RobotsDecision:
    robots_url = robots_url_for(target_url)
    try:
        result = fetcher.fetch(robots_url, accept="text/plain,*/*;q=0.1")
    except Exception as exc:
        return RobotsDecision(
            AccessPolicy.UNKNOWN,
            robots_url,
            f"robots fetch failed:{type(exc).__name__}",
        )

    if result.status_code == 404:
        return RobotsDecision(AccessPolicy.ALLOWED, robots_url, "robots.txt not present")
    if result.status_code in {401, 403}:
        return RobotsDecision(
            AccessPolicy.MANUAL_REVIEW,
            robots_url,
            f"robots.txt returned {result.status_code}",
        )
    if result.status_code >= 500:
        return RobotsDecision(
            AccessPolicy.UNKNOWN,
            robots_url,
            f"robots.txt returned {result.status_code}",
        )
    if result.status_code >= 400:
        return RobotsDecision(
            AccessPolicy.MANUAL_REVIEW,
            robots_url,
            f"robots.txt returned {result.status_code}",
        )

    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(result.text.splitlines())
    if parser.can_fetch(user_agent, target_url):
        return RobotsDecision(AccessPolicy.ALLOWED, robots_url, "robots policy allows target")
    return RobotsDecision(AccessPolicy.DISALLOWED, robots_url, "robots policy disallows target")
