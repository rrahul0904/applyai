"""Conservative remote eligibility from explicit listing evidence, never from 'remote' alone."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re


@dataclass(frozen=True)
class RemoteEligibility:
    remote_scope: str
    eligible_countries: tuple[str, ...]
    eligible_regions: tuple[str, ...]
    location_evidence: str | None
    decision: str
    reason_codes: tuple[str, ...]

    def projection(self) -> dict:
        return asdict(self)


def assess_remote_eligibility(
    *, work_mode: str | None, location: str | None = None,
    scope: str | None = None, countries: tuple[str, ...] = (),
    regions: tuple[str, ...] = (), candidate_country: str | None = None,
    candidate_regions: tuple[str, ...] = (),
) -> RemoteEligibility:
    location_evidence = " ".join((location or "").split())[:280] or None
    clean_countries = tuple(sorted({x.upper() for x in countries if re.fullmatch(r"[A-Za-z]{2}", x)}))
    clean_regions = tuple(sorted({" ".join(x.split()).upper()[:80] for x in regions if x.strip()}))
    mode = (work_mode or "").upper()
    valid_scopes = {"WORLDWIDE", "COUNTRY_RESTRICTED", "REGION_RESTRICTED", "UNKNOWN"}
    resolved_scope = (scope or "UNKNOWN").upper()
    if resolved_scope not in valid_scopes:
        resolved_scope = "UNKNOWN"
    # Location strings are posting evidence. Generic description prose is deliberately ignored.
    if resolved_scope == "UNKNOWN" and mode == "REMOTE":
        text = (location_evidence or "").casefold()
        if re.fullmatch(r"(?:remote\s*[-,:()]?\s*)?(?:worldwide|anywhere in the world|global remote)\)?", text):
            resolved_scope = "WORLDWIDE"
        else:
            match = re.fullmatch(r"remote\s*[-,:()]?\s*(US|USA|United States|UK|United Kingdom|Canada|CA|Germany|DE)\s+only\)?", location_evidence or "", re.I)
            if match:
                country_aliases = {"USA": "US", "UNITED STATES": "US", "UK": "GB", "UNITED KINGDOM": "GB", "CANADA": "CA", "GERMANY": "DE"}
                clean_countries = (country_aliases.get(match[1].upper(), match[1].upper()),)
                resolved_scope = "COUNTRY_RESTRICTED"
    reasons: tuple[str, ...]
    decision = "INCONCLUSIVE"
    if mode and mode != "REMOTE":
        resolved_scope, decision, reasons = "NOT_REMOTE", "INELIGIBLE", ("POSTING_NOT_REMOTE",)
    elif mode != "REMOTE":
        reasons = ("WORK_MODE_UNKNOWN",)
    elif resolved_scope == "WORLDWIDE" and (clean_countries or clean_regions):
        resolved_scope, reasons = "UNKNOWN", ("CONFLICTING_REMOTE_SCOPE_EVIDENCE",)
    elif resolved_scope == "WORLDWIDE":
        decision, reasons = "ELIGIBLE", ("EXPLICIT_WORLDWIDE_REMOTE",)
    elif resolved_scope == "COUNTRY_RESTRICTED" and clean_countries:
        if not candidate_country:
            reasons = ("CANDIDATE_COUNTRY_UNKNOWN",)
        else:
            decision = "ELIGIBLE" if candidate_country.upper() in clean_countries else "INELIGIBLE"
            reasons = ("COUNTRY_ALLOWED" if decision == "ELIGIBLE" else "COUNTRY_NOT_ALLOWED",)
    elif resolved_scope == "REGION_RESTRICTED" and clean_regions:
        if not candidate_regions:
            reasons = ("CANDIDATE_REGION_UNKNOWN",)
        else:
            decision = "ELIGIBLE" if set(x.upper() for x in candidate_regions) & set(clean_regions) else "INELIGIBLE"
            reasons = ("REGION_ALLOWED" if decision == "ELIGIBLE" else "REGION_NOT_ALLOWED",)
    else:
        resolved_scope, reasons = "UNKNOWN", ("REMOTE_SCOPE_UNKNOWN",)
    return RemoteEligibility(resolved_scope, clean_countries, clean_regions, location_evidence, decision, reasons)
