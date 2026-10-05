"""Validate ApplyAI release claims against SHA-scoped evidence, without cloud writes."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

STATES = (
    "RESEARCHED", "DESIGNED", "IMPLEMENTED", "REPOSITORY_VERIFIED",
    "STAGING_VERIFIED", "PRODUCTION_DEPLOYED", "PRODUCTION_CERTIFIED", "BLOCKED",
)
FIELDS = {
    "capability", "agent", "status", "repository_sha", "branch", "pr", "issue",
    "tests", "workflow_runs", "runtime_evidence", "known_gaps", "next_action", "verified_at",
}
GATES = {
    "repository": ("repository", "migrations", "security"),
    "staging": ("repository", "migrations", "security", "staging", "auth"),
    "production": (
        "repository", "migrations", "security", "staging", "auth", "human_uat", "governance",
    ),
}


def _sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _success(item: object, sha: str, environment: str | None = None) -> bool:
    return (
        isinstance(item, dict) and item.get("result") == "PASS"
        and item.get("repository_sha") == sha and bool(item.get("evidence"))
        and _timestamp(item.get("verified_at"))
        and (environment is None or item.get("environment") == environment)
    )


def validate(ledger: object, *, target: str | None = None) -> list[str]:
    """Return every malformed or unsupported claim. BLOCKED is a valid evidence state."""
    if not isinstance(ledger, dict):
        return ["Ledger must be an object"]
    errors: list[str] = []
    sha = ledger.get("release_candidate_sha")
    if not _sha(sha):
        errors.append("release_candidate_sha must be a full commit SHA")
    records = ledger.get("capabilities")
    if not isinstance(records, list) or not records:
        return errors + ["capabilities must be a nonempty array"]
    seen: set[str] = set()
    for index, record in enumerate(records):
        label = f"capabilities[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{label}: must be an object")
            continue
        missing = FIELDS - record.keys()
        if missing:
            errors.append(f"{label}: missing {', '.join(sorted(missing))}")
        capability = record.get("capability")
        if not isinstance(capability, str) or not capability.strip() or capability in seen:
            errors.append(f"{label}: capability must be nonempty and unique")
        else:
            seen.add(capability)
        state = record.get("status")
        if state not in STATES:
            errors.append(f"{label}: invalid status {state!r}")
        if not _sha(record.get("repository_sha")):
            errors.append(f"{label}: repository_sha must be a full commit SHA")
        if not _timestamp(record.get("verified_at")):
            errors.append(f"{label}: verified_at must include a timezone")
        for field in ("tests", "workflow_runs", "runtime_evidence", "known_gaps"):
            if not isinstance(record.get(field), list):
                errors.append(f"{label}: {field} must be an array")
        if state == "BLOCKED" and not record.get("known_gaps"):
            errors.append(f"{label}: BLOCKED requires an explicit gap")
        if state in STATES[3:7]:
            if record.get("repository_sha") != sha:
                errors.append(f"{label}: verified claim is for a stale release SHA")
            evidence = record.get("tests", []) + record.get("workflow_runs", []) if isinstance(record.get("tests"), list) and isinstance(record.get("workflow_runs"), list) else []
            if not any(_success(item, sha) for item in evidence):
                errors.append(f"{label}: repository verification requires successful SHA-scoped tests")
        if state in STATES[4:7]:
            runtime = record.get("runtime_evidence", [])
            if not isinstance(runtime, list) or not any(_success(item, sha, "staging") for item in runtime):
                errors.append(f"{label}: staging evidence is missing")
        if state in STATES[5:7]:
            runtime = record.get("runtime_evidence", [])
            if not isinstance(runtime, list) or not any(_success(item, sha, "production") for item in runtime):
                errors.append(f"{label}: production evidence is missing")
    if target is not None:
        gates = ledger.get("gates", {})
        if not isinstance(gates, dict):
            gates = {}
        for name in GATES[target]:
            gate = gates.get(name)
            if not _success(gate, sha):
                errors.append(f"{target} gate {name}: requires PASS for release candidate with evidence")
        if target == "production":
            uat = gates.get("human_uat", {})
            sessions = uat.get("sessions", []) if isinstance(uat, dict) else []
            verified = [item for item in sessions if isinstance(item, dict) and item.get("human") is True and item.get("participant_id") and _success(item, sha)] if isinstance(sessions, list) else []
            participants = {item["participant_id"] for item in verified}
            if len(participants) < 5:
                errors.append("production gate human_uat: requires five distinct human candidate sessions")
            deployments = ledger.get("deployments", {})
            if not isinstance(deployments, dict):
                deployments = {}
            for service in ("web", "api", "worker"):
                if not _success(deployments.get(service), sha, "production"):
                    errors.append(f"production deployment {service}: missing successful aligned runtime proof")
        issues = ledger.get("release_issues", [])
        if not isinstance(issues, list):
            errors.append("release_issues must be an array")
        elif target != "repository":
            for item in issues:
                if isinstance(item, dict) and item.get("severity") in {"BLOCKER", "P0", "P1"} and item.get("resolved") is not True:
                    errors.append(f"unresolved {item['severity']}: {item.get('title', 'unnamed issue')}")
    # Certification is always a global claim and cannot bypass deployment gates.
    if target != "production" and any(isinstance(r, dict) and r.get("status") == "PRODUCTION_CERTIFIED" for r in records):
        errors.extend(validate(ledger, target="production"))
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--target", choices=GATES)
    args = parser.parse_args()
    try:
        ledger = json.loads(args.ledger.read_text())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    errors = validate(ledger, target=args.target)
    print(json.dumps({"status": "FAIL" if errors else "PASS", "target": args.target or "structure", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
