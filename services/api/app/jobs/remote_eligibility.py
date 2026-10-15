"""Conservative remote eligibility from explicit listing evidence, never from 'remote' alone."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import re


@dataclass(frozen=True)
class RemoteEligibility:
    remote_scope: str
    eligible_countries: tuple[str, ...]
    eligible_regions: tuple[str, ...]
    location_evidence: str | None
    decision: str
    reason_codes: tuple[str, ...]
    selected_source_url: str | None = None
    source_authority: str | None = None
    conflicting_source_urls: tuple[str, ...] = ()

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
    mode = (work_mode or "").strip().upper()
    if mode not in {"REMOTE", "HYBRID", "ONSITE"}:
        mode = ""
    candidate_country = candidate_country.strip().upper() if candidate_country else None
    if candidate_country and not re.fullmatch(r"[A-Z]{2}", candidate_country):
        candidate_country = None
    valid_scopes = {"WORLDWIDE", "COUNTRY_RESTRICTED", "REGION_RESTRICTED", "UNKNOWN"}
    resolved_scope = (scope or "UNKNOWN").upper()
    if resolved_scope not in valid_scopes:
        resolved_scope = "UNKNOWN"
    # Location restrictions remain evidence even if a provider supplied a broader scope.
    location_scope, location_countries = "UNKNOWN", ()
    if mode == "REMOTE":
        text = (location_evidence or "").casefold()
        if re.fullmatch(r"(?:remote\s*[-,:()]?\s*)?(?:worldwide|anywhere in the world|global remote)\)?", text):
            location_scope = "WORLDWIDE"
        else:
            match = re.fullmatch(r"remote\s*[-,:()]?\s*(US|USA|United States|UK|United Kingdom|Canada|CA|Germany|DE)\s+only\)?", location_evidence or "", re.I)
            if match:
                country_aliases = {"USA": "US", "UNITED STATES": "US", "UK": "GB", "UNITED KINGDOM": "GB", "CANADA": "CA", "GERMANY": "DE"}
                location_countries = (country_aliases.get(match[1].upper(), match[1].upper()),)
                location_scope = "COUNTRY_RESTRICTED"
    contradictory_location = (
        resolved_scope != "UNKNOWN" and location_scope != "UNKNOWN"
        and (resolved_scope != location_scope or (location_scope == "COUNTRY_RESTRICTED" and clean_countries and set(clean_countries) != set(location_countries)))
    )
    if resolved_scope == "UNKNOWN" and location_scope != "UNKNOWN":
        resolved_scope, clean_countries = location_scope, location_countries
    reasons: tuple[str, ...]
    decision = "INCONCLUSIVE"
    if mode and mode != "REMOTE":
        resolved_scope, decision, reasons = "NOT_REMOTE", "INELIGIBLE", ("POSTING_NOT_REMOTE",)
    elif mode != "REMOTE":
        reasons = ("WORK_MODE_UNKNOWN",)
    elif len(clean_countries) != len(set(x.upper() for x in countries)):
        resolved_scope, reasons = "UNKNOWN", ("INVALID_COUNTRY_EVIDENCE",)
    elif clean_countries and clean_regions:
        resolved_scope, reasons = "UNKNOWN", ("MULTIPLE_GEOGRAPHIC_CONSTRAINTS_UNRESOLVED",)
    elif contradictory_location:
        resolved_scope, reasons = "UNKNOWN", ("CONFLICTING_REMOTE_SCOPE_EVIDENCE",)
    elif resolved_scope == "WORLDWIDE" and (clean_countries or clean_regions):
        resolved_scope, reasons = "UNKNOWN", ("CONFLICTING_REMOTE_SCOPE_EVIDENCE",)
    elif resolved_scope == "WORLDWIDE":
        decision, reasons = "ELIGIBLE", ("EXPLICIT_WORLDWIDE_REMOTE",)
    elif resolved_scope == "COUNTRY_RESTRICTED" and clean_countries:
        if not candidate_country:
            reasons = ("CANDIDATE_COUNTRY_UNKNOWN",)
        else:
            decision = "ELIGIBLE" if candidate_country.strip().upper() in clean_countries else "INELIGIBLE"
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


@dataclass(frozen=True)
class RemoteSourceEvidence:
    """Caller-resolved canonical identity and authority; no authority inferred from URL branding."""
    canonical_job_id: str
    source_url: str
    authority: str  # EMPLOYER, ATS, AGGREGATOR, UNKNOWN
    work_mode: str | None = None
    location: str | None = None
    scope: str | None = None
    countries: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()


def assess_remote_sources(
    *, canonical_job_id: str, sources: tuple[RemoteSourceEvidence, ...],
    candidate_country: str | None = None, candidate_regions: tuple[str, ...] = (),
) -> RemoteEligibility:
    """Use employer/ATS facts before aggregator aliases; tied conflicting facts fail closed.

    An unknown employer restriction cannot be replaced with an aggregator's worldwide claim.
    Authority and canonical identity must come from ApplyAI's reviewed source registry.
    """
    from app.jobs.opportunity_lifecycle import public_source_url

    rank = {"EMPLOYER": 3, "ATS": 3, "AGGREGATOR": 1, "UNKNOWN": 0}
    eligible = [source for source in sources if source.canonical_job_id == canonical_job_id
                and public_source_url(source.source_url)]
    if not eligible:
        return RemoteEligibility("UNKNOWN", (), (), None, "INCONCLUSIVE", ("NO_CANONICAL_SOURCE_EVIDENCE",))
    selected_rank = max(rank.get(source.authority.upper(), 0) for source in eligible)
    peers = sorted((source for source in eligible if rank.get(source.authority.upper(), 0) == selected_rank),
                   key=lambda source: public_source_url(source.source_url) or "")
    results = [(source, assess_remote_eligibility(work_mode=source.work_mode, location=source.location,
               scope=source.scope, countries=source.countries, regions=source.regions,
               candidate_country=candidate_country, candidate_regions=candidate_regions)) for source in peers]
    def signature(result: RemoteEligibility) -> tuple:
        return result.remote_scope, result.eligible_countries, result.eligible_regions, result.decision
    selected_source, selected = results[0]
    if selected_rank == 0:
        return RemoteEligibility("UNKNOWN", (), (), None, "INCONCLUSIVE", ("UNVERIFIED_SOURCE_AUTHORITY",))
    if len({signature(result) for _, result in results}) != 1:
        return RemoteEligibility("UNKNOWN", (), (), None, "INCONCLUSIVE", ("CONFLICTING_AUTHORITATIVE_SOURCES",),
                                 None, selected_source.authority.upper(),
                                 tuple(sorted({public_source_url(source.source_url) for source, _ in results})))
    conflicts = []
    for source in eligible:
        if rank.get(source.authority.upper(), 0) >= selected_rank:
            continue
        lower = assess_remote_eligibility(work_mode=source.work_mode, location=source.location, scope=source.scope,
                countries=source.countries, regions=source.regions, candidate_country=candidate_country,
                candidate_regions=candidate_regions)
        if signature(lower) != signature(selected):
            conflicts.append(public_source_url(source.source_url))
    return replace(selected, selected_source_url=public_source_url(selected_source.source_url),
                   source_authority=selected_source.authority.upper(),
                   conflicting_source_urls=tuple(sorted(set(conflicts))),
                   reason_codes=selected.reason_codes + (("LOWER_AUTHORITY_CONFLICT_IGNORED",) if conflicts else ()))
