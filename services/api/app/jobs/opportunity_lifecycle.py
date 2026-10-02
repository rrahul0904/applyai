"""Evidence decisions and read-only lifecycle projections over canonical jobs.

Search absence never constitutes closure evidence, including a complete search response.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from collections import Counter
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class OpportunityEvidence:
    observed_at: datetime
    source_url: str
    observation: str  # OPEN, EXPLICIT_CLOSED, SEARCH_ABSENT, ERROR
    coverage: str = "INCONCLUSIVE"
    authoritative: bool = False
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpportunityDecision:
    state: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class OpportunityLifecycle:
    state: str
    first_seen: datetime
    last_seen: datetime
    closed_at: datetime | None = None
    reason_codes: tuple[str, ...] = ()

    def projection(self) -> dict:
        value = asdict(self)
        for field in ("first_seen", "last_seen", "closed_at"):
            value[field] = value[field].isoformat() if value[field] else None
        return value


def decide_opportunity(evidence: OpportunityEvidence) -> OpportunityDecision:
    if evidence.observation == "OPEN":
        return OpportunityDecision("OPEN", ("EXPLICIT_OPEN_OBSERVATION",))
    if evidence.observation == "EXPLICIT_CLOSED" and evidence.authoritative and evidence.coverage == "COMPLETE":
        return OpportunityDecision("CLOSED", ("AUTHORITATIVE_EXPLICIT_CLOSURE",))
    if evidence.observation == "SEARCH_ABSENT":
        return OpportunityDecision("INCONCLUSIVE", ("SEARCH_ABSENCE_NOT_CLOSURE",))
    return OpportunityDecision("INCONCLUSIVE", evidence.reason_codes or ("INSUFFICIENT_CLOSURE_EVIDENCE",))


def advance_lifecycle(current: OpportunityLifecycle, evidence: OpportunityEvidence) -> OpportunityLifecycle:
    watermark = max(current.last_seen, current.closed_at) if current.closed_at else current.last_seen
    if evidence.observed_at < watermark:
        return current
    decision = decide_opportunity(evidence)
    if decision.state == "INCONCLUSIVE":
        # Keep verified availability and last seen; failed observations are not sightings.
        return replace(current, reason_codes=decision.reason_codes)
    if decision.state == "CLOSED":
        return replace(current, state="CLOSED", closed_at=evidence.observed_at, reason_codes=decision.reason_codes)
    reopened = current.state == "CLOSED"
    if reopened and not evidence.authoritative:
        return replace(current, reason_codes=("NON_AUTHORITATIVE_REOPEN_IGNORED",))
    return replace(current, state="REOPENED" if reopened else "OPEN", last_seen=evidence.observed_at, closed_at=None,
                   reason_codes=("EXPLICIT_REOPEN_OBSERVATION",) if reopened else decision.reason_codes)


def public_source_url(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value or "")
        if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
            return None
        # Provenance never exposes query tokens, credentials or fragments.
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))[:2048]
    except ValueError:
        return None


def lifecycle_metrics(items: list[dict]) -> dict[str, int]:
    counts = Counter(item.get("state", "INCONCLUSIVE") for item in items)
    return {state.lower(): counts[state] for state in ("OPEN", "CLOSED", "REOPENED", "INCONCLUSIVE")}


def sanitized_match_evidence(raw: dict) -> dict:
    """Allowlist the publication contract instead of publishing provider payloads/checkpoints."""
    out = {}
    for key, maximum in (("provider", 80), ("provider_job_id", 160), ("title", 280), ("company", 240), ("location", 280), ("work_mode", 32), ("employment_type", 48), ("seniority", 48), ("explanation", 500)):
        value = raw.get(key)
        if isinstance(value, str):
            out[key] = " ".join(value.split())[:maximum]
    if isinstance(raw.get("skills"), (tuple, list)):
        out["skills"] = [" ".join(value.split())[:120] for value in raw["skills"][:40] if isinstance(value, str) and value.strip()]
    out["application_url"] = public_source_url(raw.get("application_url"))
    salary = raw.get("salary")
    out["salary"] = None
    if isinstance(salary, dict):
        out["salary"] = {}
        for key in ("minimum", "maximum"):
            entry = salary.get(key)
            if entry is None or (isinstance(entry, (int, float)) and not isinstance(entry, bool)):
                out["salary"][key] = entry
        for key in ("currency", "interval", "raw", "provenance"):
            entry = salary.get(key)
            if isinstance(entry, str):
                out["salary"][key] = " ".join(entry.split())[:280]
    for name, fields in {
        "remote_eligibility": ("remote_scope", "eligible_countries", "eligible_regions", "location_evidence", "decision", "reason_codes", "selected_source_url", "source_authority", "conflicting_source_urls"),
        "opportunity": ("state", "first_seen", "last_seen", "closed_at", "reason_codes"),
    }.items():
        value = raw.get(name)
        if isinstance(value, dict):
            projected = {}
            for key in fields:
                entry = value.get(key)
                if key in {"eligible_countries", "eligible_regions", "reason_codes", "conflicting_source_urls"}:
                    if isinstance(entry, (tuple, list)):
                        projected[key] = [" ".join(item.split())[:280] for item in entry[:40] if isinstance(item, str)]
                elif entry is None or isinstance(entry, str):
                    projected[key] = " ".join(entry.split())[:500] if isinstance(entry, str) else None
            if name == "remote_eligibility":
                projected["selected_source_url"] = public_source_url(value.get("selected_source_url"))
                projected["conflicting_source_urls"] = [url for item in projected.get("conflicting_source_urls", []) if (url := public_source_url(item))]
            out[name] = projected
    provenance = raw.get("provenance")
    if isinstance(provenance, dict):
        out["provenance"] = {}
        for key in ("canonical_sources", "aggregator_sources"):
            entries = provenance.get(key, [])
            out["provenance"][key] = list(dict.fromkeys(url for value in entries[:40]
                if isinstance(value, str) and (url := public_source_url(value)))) if isinstance(entries, (tuple, list)) else []
    return out
