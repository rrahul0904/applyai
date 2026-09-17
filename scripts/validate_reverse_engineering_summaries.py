from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "reverse-engineering"
VALID_FITS = {"CORE", "PREPARE", "INTELLIGENCE", "INFRASTRUCTURE", "INTEGRATION", "NOT_APPLYAI"}
VALID_SCOPES = {"FULL", "PARTIAL", "NONE"}
REQUIRED_FRONTMATTER = {"applyai_fit", "fit_scope", "destination"}
REQUIRED_HEADINGS = (
    "ApplyAI Fit",
    "Why this qualifies",
    "Candidate journey stages",
    "Absorb into ApplyAI",
    "Keep separate",
    "Implementation destination",
    "Implementation status",
)


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    meta = frontmatter(text)
    errors: list[str] = []
    missing = sorted(REQUIRED_FRONTMATTER - meta.keys())
    if missing:
        errors.append(f"missing frontmatter: {', '.join(missing)}")
    if meta.get("applyai_fit") not in VALID_FITS:
        errors.append(f"invalid applyai_fit: {meta.get('applyai_fit')!r}")
    if meta.get("fit_scope") not in VALID_SCOPES:
        errors.append(f"invalid fit_scope: {meta.get('fit_scope')!r}")
    if not meta.get("destination"):
        errors.append("destination must not be empty")
    for heading in REQUIRED_HEADINGS:
        if not re.search(rf"^##\s+{re.escape(heading)}\s*$", text, flags=re.MULTILINE):
            errors.append(f"missing heading: ## {heading}")
    return errors


def main() -> int:
    if not DOCS.exists():
        print("No reverse-engineering summary directory found.")
        return 0
    summaries = sorted(path for path in DOCS.rglob("*.md") if path.name != "README.md")
    failures = 0
    for path in summaries:
        errors = validate(path)
        if not errors:
            print(f"OK {path.relative_to(ROOT)}")
            continue
        failures += 1
        print(f"FAIL {path.relative_to(ROOT)}")
        for error in errors:
            print(f"  - {error}")
    if failures:
        print(f"{failures} reverse-engineering summary file(s) failed validation.")
        return 1
    print(f"Validated {len(summaries)} reverse-engineering summary file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
