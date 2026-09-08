from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.validate_supabase_policies import repository_root

PROVIDERS = ("clerk", "railway")

TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".md",
    ".sh",
    ".sql",
    ".env",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    ".venv",
    "node_modules",
    "playwright-report",
    "test-results",
    "artifacts",
}

RUNTIME_PREFIXES = (
    "apps/web/",
    "services/api/app/",
    "services/api/scripts/",
    ".github/workflows/",
)

RUNTIME_MANIFESTS = {
    "apps/web/package.json",
    "services/api/pyproject.toml",
    "pnpm-lock.yaml",
}

ALLOWED_FINAL_RUNTIME_MATCHES = {
    # Legacy identity is retained only as a data-migration compatibility column and can be
    # removed in a later irreversible data-retention migration.
    "services/api/app/models.py": {"clerk_user_id"},
    "services/api/app/core/auth.py": set(),
}


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {
            ".env.example",
            "Dockerfile",
        }:
            yield relative, path


def is_runtime_path(relative: str) -> bool:
    return relative in RUNTIME_MANIFESTS or relative.startswith(RUNTIME_PREFIXES)


def scan_provider(provider: str, root: Path) -> dict[str, object]:
    pattern = re.compile(re.escape(provider), re.IGNORECASE)
    matches: list[dict[str, object]] = []
    runtime_matches: list[dict[str, object]] = []

    for relative, path in iter_text_files(root):
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if not pattern.search(line):
                continue
            evidence = {
                "path": relative,
                "line": line_number,
                "text": line.strip()[:240],
            }
            matches.append(evidence)
            if is_runtime_path(relative):
                runtime_matches.append(evidence)

    return {
        "provider": provider,
        "total_matches": len(matches),
        "runtime_matches": runtime_matches,
        "all_matches": matches,
    }


def final_runtime_blockers(provider_report: dict[str, object]) -> list[dict[str, object]]:
    provider = str(provider_report["provider"])
    blockers: list[dict[str, object]] = []
    for match in provider_report["runtime_matches"]:
        path = str(match["path"])
        text = str(match["text"])
        allowed_tokens = ALLOWED_FINAL_RUNTIME_MATCHES.get(path)
        if provider == "clerk" and allowed_tokens is not None:
            if allowed_tokens and any(token in text for token in allowed_tokens):
                continue
        blockers.append(match)
    return blockers


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Clerk/Railway references and optionally require zero runtime dependency."
    )
    parser.add_argument(
        "--report",
        default="artifacts/provider-dependency-audit.json",
    )
    parser.add_argument(
        "--require-removed",
        action="store_true",
        help="Fail if Clerk or Railway still has production runtime references.",
    )
    args = parser.parse_args()

    root = repository_root()
    providers = [scan_provider(provider, root) for provider in PROVIDERS]
    blockers = {
        report["provider"]: final_runtime_blockers(report)
        for report in providers
    }
    status = (
        "PASS"
        if not args.require_removed or not any(blockers.values())
        else "BLOCKED"
    )
    report = {
        "schema_version": 1,
        "mode": "require-removed" if args.require_removed else "inventory",
        "providers": providers,
        "runtime_blockers": blockers,
        "status": status,
    }
    path = root / args.report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
