from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class SourceSpec:
    source_type: str
    identity: str
    base_url: str
    configuration: dict

    @property
    def source_name(self) -> str:
        return f"{self.source_type.title()}: {self.identity}"


def parse_json_list(name: str) -> list[str]:
    value = os.getenv(name, "[]")
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError(f"{name} must be a JSON array of strings")
    return [item.strip() for item in parsed if item.strip()]


def source_specs() -> list[SourceSpec]:
    results: list[SourceSpec] = []
    for token in parse_json_list("GREENHOUSE_BOARD_TOKENS"):
        results.append(
            SourceSpec(
                "GREENHOUSE",
                token,
                f"https://boards.greenhouse.io/{token}",
                {"board_token": token},
            )
        )
    for site in parse_json_list("LEVER_SITE_NAMES"):
        results.append(
            SourceSpec(
                "LEVER",
                site,
                f"https://jobs.lever.co/{site}",
                {"site": site, "region": "global", "max_pages": 20},
            )
        )
    for board in parse_json_list("ASHBY_BOARD_NAMES"):
        results.append(
            SourceSpec(
                "ASHBY",
                board,
                f"https://jobs.ashbyhq.com/{board}",
                {"board_name": board, "include_compensation": True},
            )
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("API_BASE_URL"),
        help="ApplyAI staging API base URL",
    )
    parser.add_argument(
        "--operator-token",
        default=os.getenv("INTERNAL_API_TOKEN"),
        help="Internal operator token; prefer the environment variable",
    )
    parser.add_argument("--interval-seconds", type=int, default=21_600)
    parser.add_argument("--max-per-provider", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.api_base_url:
        raise SystemExit("API_BASE_URL or --api-base-url is required")
    if not args.operator_token and not args.dry_run:
        raise SystemExit("INTERNAL_API_TOKEN or --operator-token is required")

    counts: dict[str, int] = {}
    selected: list[SourceSpec] = []
    for spec in source_specs():
        count = counts.get(spec.source_type, 0)
        if count >= args.max_per_provider:
            continue
        counts[spec.source_type] = count + 1
        selected.append(spec)

    if args.dry_run:
        print(
            json.dumps(
                [
                    {
                        "source_type": spec.source_type,
                        "source_identity": spec.identity,
                        "base_url": spec.base_url,
                    }
                    for spec in selected
                ],
                indent=2,
            )
        )
        return

    headers = {"X-ApplyAI-Internal-Token": args.operator_token}
    with httpx.Client(
        base_url=args.api_base_url.rstrip("/"),
        headers=headers,
        timeout=20,
    ) as client:
        registered: list[dict] = []
        for spec in selected:
            response = client.post(
                "/api/v1/internal/job-sources",
                json={
                    "source_type": spec.source_type,
                    "source_name": spec.source_name,
                    "source_identity": spec.identity,
                    "base_url": spec.base_url,
                    "configuration": spec.configuration,
                    "trust_level": "OFFICIAL_ATS",
                    "enabled": True,
                    "crawl_allowed": True,
                    "crawl_interval_seconds": args.interval_seconds,
                },
            )
            response.raise_for_status()
            payload = response.json()
            registered.append(
                {
                    "id": payload["id"],
                    "source_type": payload["source_type"],
                    "source_identity": payload["source_identity"],
                    "enabled": payload["enabled"],
                }
            )
    print(json.dumps({"registered": registered}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
