#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "predeploy"
REPORT_PATH = ARTIFACT_DIR / "full-functional-contract.json"


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8", errors="replace")


def any_text(glob_pattern: str) -> str:
    chunks: list[str] = []
    for path in ROOT.glob(glob_pattern):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def check_file(name: str, path: str, tokens: tuple[str, ...] = ()) -> dict:
    target = ROOT / path
    content = read(path)
    missing_tokens = [token for token in tokens if token.casefold() not in content.casefold()]
    ok = target.is_file() and not missing_tokens
    return {
        "name": name,
        "ok": ok,
        "path": path,
        "missing_tokens": missing_tokens,
    }


def check_glob(name: str, glob_pattern: str, tokens: tuple[str, ...]) -> dict:
    content = any_text(glob_pattern)
    missing_tokens = [token for token in tokens if token.casefold() not in content.casefold()]
    matches = [str(path.relative_to(ROOT)) for path in ROOT.glob(glob_pattern) if path.is_file()]
    return {
        "name": name,
        "ok": bool(matches) and not missing_tokens,
        "glob": glob_pattern,
        "matched_files": matches,
        "missing_tokens": missing_tokens,
    }


def main() -> int:
    checks = [
        check_file(
            "durable SOURCE_INGEST worker",
            "services/api/app/workers/source.py",
            ("SOURCE_INGEST", "process_source_ingest"),
        ),
        check_file(
            "durable task outbox",
            "services/api/app/core/outbox.py",
            ("add_task_outbox_event", "publish_outbox_once"),
        ),
        check_file(
            "operations API",
            "services/api/app/api/internal_operations.py",
            ("refresh", "certification", "cursor"),
        ),
        check_file(
            "operations UI",
            "apps/web/app/admin/operations/page.tsx",
            ("Jobs", "Sources", "Ingestion", "Certification"),
        ),
        check_glob(
            "persisted operations/certification migration",
            "services/api/**/versions/*.py",
            ("certif",),
        ),
        check_glob(
            "operations backend tests",
            "services/api/tests/test_*.py",
            ("internal_operations", "SOURCE_INGEST", "certif"),
        ),
        check_glob(
            "operations browser E2E",
            "apps/web/e2e/*.ts",
            ("admin/operations",),
        ),
        check_file(
            "candidate browser E2E",
            "apps/web/e2e/candidate-mvp.spec.ts",
        ),
        check_file(
            "clean-room certification harness",
            "scripts/local-certify.sh",
            ("PostgreSQL", "background workers", "playwright"),
        ),
        check_file(
            "demo screenshot workflow",
            ".github/workflows/demo-capture.yml",
            ("Upload demo screenshots", "playwright"),
        ),
    ]

    package = read("package.json")
    package_scripts = {
        "local:certify": '"local:certify"' in package,
        "test:e2e": '"test:e2e"' in package,
        "openapi:check": '"openapi:check"' in package,
        "test:api": '"test:api"' in package,
        "release:predeploy-certify": '"release:predeploy-certify"' in package,
    }
    checks.append(
        {
            "name": "required package scripts",
            "ok": all(package_scripts.values()),
            "scripts": package_scripts,
        }
    )

    failures = [item for item in checks if not item["ok"]]
    report = {
        "status": "PASS" if not failures else "FAIL",
        "git_sha": os.getenv("GITHUB_SHA") or os.getenv("VERCEL_GIT_COMMIT_SHA"),
        "vercel_deployment": "NOT_PERFORMED_INTENTIONALLY_EXCLUDED",
        "checks": checks,
        "failures": failures,
        "claim": (
            "REPO_FUNCTIONAL_CONTRACT_PRESENT"
            if not failures
            else "REPO_FUNCTIONAL_CONTRACT_INCOMPLETE"
        ),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"Contract report: {REPORT_PATH.relative_to(ROOT)}")

    if failures:
        print("\nFAIL: ApplyAI full-functional contract is incomplete.", file=sys.stderr)
        for item in failures:
            print(f"- {item['name']}", file=sys.stderr)
        return 2

    print("\nPASS: ApplyAI full-functional repository contract is present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
