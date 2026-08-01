from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_DIR = ROOT / "docs" / "benchmarks"
OUTPUT = ROOT / "docs" / "JOB_DATA_PLATFORM_EXECUTED_BENCHMARKS.md"


def load(name: str) -> dict:
    return json.loads((BENCHMARK_DIR / name).read_text(encoding="utf-8"))


def fmt_number(value, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{float(value):,.{digits}f}"


def query_table(report: dict) -> str:
    rows = [
        "| Query | Planning ms | Execution ms | Node | Actual rows | Shared hits | Shared reads |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for name, result in report["queries"].items():
        rows.append(
            "| {name} | {planning} | {execution} | {node} | {actual} | {hits} | {reads} |".format(
                name=name.replace("_", " ").title(),
                planning=fmt_number(result.get("planning_time_ms")),
                execution=fmt_number(result.get("execution_time_ms")),
                node=result.get("node_type") or "—",
                actual=fmt_number(result.get("actual_rows"), 0),
                hits=fmt_number(result.get("shared_hit_blocks"), 0),
                reads=fmt_number(result.get("shared_read_blocks"), 0),
            )
        )
    return "\n".join(rows)


def section(size: int, report: dict) -> str:
    return f"""## {size:,} synthetic canonical jobs

- Inserted rows: **{fmt_number(report.get('inserted_rows'), 0)}**
- Seed time: **{fmt_number(report.get('seed_seconds'), 4)} seconds**
- Database size after seed: **{fmt_number(report.get('database_bytes_after_seed'), 0)} bytes**
- Environment: `{report.get('environment', 'unknown')}`

{query_table(report)}
"""


def main() -> None:
    source_gate = load("prompt3-source-gate.json")
    extended = load("prompt3-extended-scale-gate.json")
    reports = {
        10_000: source_gate["benchmark"],
        50_000: extended["benchmarks"]["50000"],
        250_000: extended["benchmarks"]["250000"],
    }
    content = f"""# ApplyAI Executed PostgreSQL Job Search Benchmarks

This document is generated only from committed executable benchmark evidence.

## Evidence identity

- 10K source gate status: **{source_gate['status']}**
- 10K tested SHA: `{source_gate['tested_sha']}`
- 10K recorded at: `{source_gate['recorded_at']}`
- Extended scale status: **{extended['status']}**
- Extended tested SHA: `{extended['tested_sha']}`
- Extended recorded at: `{extended['recorded_at']}`

## Interpretation boundary

These are synthetic, non-production PostgreSQL measurements on GitHub-hosted runners. They prove the queries executed at the stated row counts. They do **not** prove Aurora capacity, live-provider quality, one-million-job support, AWS cost, or production latency.

{section(10_000, reports[10_000])}

{section(50_000, reports[50_000])}

{section(250_000, reports[250_000])}

## Search-engine decision

PostgreSQL remains the search backend. Any future OpenSearch proposal must begin with a measured PostgreSQL limitation and an explicit cost/operational comparison.
"""
    OUTPUT.write_text(content, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
