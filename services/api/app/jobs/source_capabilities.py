from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.global_job_supply_models import JobSourceCapability


class SourceAccessMode(StrEnum):
    DIRECT_PUBLIC_API = "DIRECT_PUBLIC_API"
    AUTHORIZED_FEED = "AUTHORIZED_FEED"
    PARTNER_API = "PARTNER_API"
    LICENSED_IMPORT = "LICENSED_IMPORT"
    PUBLIC_ATS = "PUBLIC_ATS"
    PUBLIC_STRUCTURED_PAGE = "PUBLIC_STRUCTURED_PAGE"
    EMPLOYER_CAREER_SITE = "EMPLOYER_CAREER_SITE"
    FIRST_PARTY_APPLYAI = "FIRST_PARTY_APPLYAI"
    PARTNERSHIP_REQUIRED = "PARTNERSHIP_REQUIRED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    UNSUPPORTED = "UNSUPPORTED"


class ProviderImplementationStatus(StrEnum):
    SOURCE_DESIGNED = "SOURCE_DESIGNED"
    SOURCE_IMPLEMENTED = "SOURCE_IMPLEMENTED"
    SOURCE_TESTED = "SOURCE_TESTED"
    LIVE_PUBLIC_SOURCE_VERIFIED = "LIVE_PUBLIC_SOURCE_VERIFIED"
    LIVE_STAGING_VERIFIED = "LIVE_STAGING_VERIFIED"
    PRODUCTION_VERIFIED = "PRODUCTION_VERIFIED"
    PARTNERSHIP_REQUIRED = "PARTNERSHIP_REQUIRED"
    BLOCKED_BY_PROVIDER_POLICY = "BLOCKED_BY_PROVIDER_POLICY"
    NOT_YET_SUPPORTED = "NOT_YET_SUPPORTED"


@dataclass(frozen=True)
class ProviderCapabilitySeed:
    provider_key: str
    display_name: str
    access_mode: SourceAccessMode
    implementation_status: ProviderImplementationStatus
    official_api_available: bool = False
    public_feed_available: bool = False
    partner_feed_available: bool = False
    public_page_access: bool = False
    authentication_required: bool = False
    requires_partnership: bool = False
    robots_policy: str = "SOURCE_SPECIFIC"
    rate_limit_policy: str = "PROVIDER_SPECIFIC"
    pagination_strategy: str = "PROVIDER_SPECIFIC"
    supports_delta: bool = False
    supports_closure_detection: bool = False
    trust_level: str = "UNVERIFIED_PUBLIC_SOURCE"
    allowed_for_automated_ingestion: bool = False
    recommended_strategy: str = ""
    documentation_url: str | None = None
    notes: str | None = None
    reason: str | None = None


def employer_career(
    key: str,
    name: str,
    *,
    notes: str | None = None,
) -> ProviderCapabilitySeed:
    return ProviderCapabilitySeed(
        key,
        name,
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        public_page_access=True,
        robots_policy="ROBOTS_AND_SOURCE_POLICY_REQUIRED",
        rate_limit_policy="PER_DOMAIN_BOUNDED",
        pagination_strategy="BOUNDED_DISCOVERY",
        supports_closure_detection=True,
        trust_level="EMPLOYER_CAREER_SITE",
        allowed_for_automated_ingestion=True,
        recommended_strategy=(
            "Detect the employer ATS and ingest only bounded public job pages through the "
            "robots-aware generic career-site connector unless a dedicated documented public API is available."
        ),
        notes=notes,
        reason="Employer-origin public page; runtime policy and robots checks remain mandatory.",
    )


def partnership(
    key: str,
    name: str,
    *,
    official_api: bool = False,
    partner_feed: bool = True,
    auth: bool = True,
    docs: str | None = None,
    notes: str | None = None,
) -> ProviderCapabilitySeed:
    return ProviderCapabilitySeed(
        key,
        name,
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        official_api_available=official_api,
        partner_feed_available=partner_feed,
        authentication_required=auth,
        requires_partnership=True,
        rate_limit_policy="CONTRACT_SPECIFIC",
        pagination_strategy="CONTRACT_SPECIFIC",
        supports_closure_detection=False,
        trust_level="AUTHORIZED_AGGREGATOR_FEED",
        allowed_for_automated_ingestion=False,
        recommended_strategy=(
            "Use an authorized/licensed provider integration when contracted; otherwise resolve "
            "the opportunity to the original employer ATS or employer career page. Do not bypass access controls."
        ),
        documentation_url=docs,
        notes=notes,
        reason="No anonymous crawler is authorized by ApplyAI policy for this provider.",
    )


PROVIDER_CAPABILITY_SEEDS: tuple[ProviderCapabilitySeed, ...] = (
    ProviderCapabilitySeed(
        "applyai",
        "ApplyAI first-party employers",
        SourceAccessMode.FIRST_PARTY_APPLYAI,
        ProviderImplementationStatus.SOURCE_TESTED,
        supports_delta=True,
        supports_closure_detection=True,
        trust_level="APPLYAI_FIRST_PARTY",
        allowed_for_automated_ingestion=True,
        recommended_strategy="Use ApplyAI employer-published jobs as canonical highest-authority observations.",
        reason="First-party employer publication managed by ApplyAI.",
    ),
    ProviderCapabilitySeed(
        "greenhouse",
        "Greenhouse",
        SourceAccessMode.PUBLIC_ATS,
        ProviderImplementationStatus.SOURCE_TESTED,
        official_api_available=True,
        public_page_access=True,
        rate_limit_policy="BOUNDED_WITH_RETRY_AFTER",
        pagination_strategy="PUBLIC_JOB_BOARD_LIST",
        supports_closure_detection=True,
        trust_level="OFFICIAL_ATS",
        allowed_for_automated_ingestion=True,
        recommended_strategy="Use the documented public Job Board API for published employer jobs.",
        documentation_url="https://developers.greenhouse.io/job-board.html",
        reason="Documented public employer job-board API.",
    ),
    ProviderCapabilitySeed(
        "lever",
        "Lever",
        SourceAccessMode.PUBLIC_ATS,
        ProviderImplementationStatus.SOURCE_TESTED,
        official_api_available=True,
        public_page_access=True,
        rate_limit_policy="BOUNDED_WITH_429_BACKOFF",
        pagination_strategy="PUBLIC_POSTINGS_PAGINATION",
        supports_closure_detection=True,
        trust_level="OFFICIAL_ATS",
        allowed_for_automated_ingestion=True,
        recommended_strategy="Use the public postings API for employer sites; do not automate private recruiting APIs.",
        documentation_url="https://github.com/lever/postings-api",
        reason="Published employer job postings are exposed through the public postings API.",
    ),
    ProviderCapabilitySeed(
        "ashby",
        "Ashby",
        SourceAccessMode.PUBLIC_ATS,
        ProviderImplementationStatus.SOURCE_TESTED,
        official_api_available=True,
        public_page_access=True,
        rate_limit_policy="BOUNDED_PROVIDER_SPECIFIC",
        pagination_strategy="PUBLIC_JOB_BOARD",
        supports_closure_detection=True,
        trust_level="OFFICIAL_ATS",
        allowed_for_automated_ingestion=True,
        recommended_strategy="Use Ashby's public job-board posting endpoint for published jobs.",
        documentation_url="https://developers.ashbyhq.com/docs/public-job-posting-api",
        reason="Public employer job-board interface.",
    ),
    ProviderCapabilitySeed(
        "smartrecruiters",
        "SmartRecruiters",
        SourceAccessMode.PUBLIC_ATS,
        ProviderImplementationStatus.SOURCE_TESTED,
        official_api_available=True,
        public_page_access=True,
        rate_limit_policy="BOUNDED_WITH_PROVIDER_LIMITS",
        pagination_strategy="OFFSET_LIMIT",
        supports_closure_detection=True,
        trust_level="OFFICIAL_ATS",
        allowed_for_automated_ingestion=True,
        recommended_strategy="Use the public Posting API list/detail endpoints for active public company postings.",
        documentation_url="https://developers.smartrecruiters.com/docs/endpoints",
        reason="Public posting endpoints are supported by the dedicated adapter.",
    ),
    ProviderCapabilitySeed(
        "usajobs",
        "USAJOBS",
        SourceAccessMode.DIRECT_PUBLIC_API,
        ProviderImplementationStatus.SOURCE_TESTED,
        official_api_available=True,
        authentication_required=True,
        rate_limit_policy="OFFICIAL_API_KEY_QUOTA",
        pagination_strategy="PAGE_RESULTS_PER_PAGE",
        supports_closure_detection=True,
        trust_level="GOVERNMENT_OFFICIAL",
        allowed_for_automated_ingestion=True,
        recommended_strategy="Use the official Search API with an issued API key and configured user agent.",
        documentation_url="https://developer.usajobs.gov/api-reference/get-api-search",
        reason="Official government job-search API; staging requires issued credentials.",
    ),
    ProviderCapabilitySeed(
        "reliefweb",
        "ReliefWeb",
        SourceAccessMode.DIRECT_PUBLIC_API,
        ProviderImplementationStatus.SOURCE_TESTED,
        official_api_available=True,
        authentication_required=True,
        rate_limit_policy="APPNAME_QUOTA",
        pagination_strategy="OFFSET_LIMIT",
        supports_closure_detection=True,
        trust_level="AUTHORIZED_AGGREGATOR_FEED",
        allowed_for_automated_ingestion=True,
        recommended_strategy="Use the official ReliefWeb v2 jobs API with a pre-approved appname and quota-aware paging.",
        documentation_url="https://apidoc.reliefweb.int/",
        reason="Official humanitarian jobs API; staging requires an approved appname.",
    ),
    employer_career("workday", "Workday"),
    employer_career("workable", "Workable"),
    employer_career("icims", "iCIMS"),
    employer_career("oracle", "Oracle Recruiting"),
    employer_career("successfactors", "SAP SuccessFactors"),
    employer_career("jobvite", "Jobvite"),
    employer_career("ukg", "UKG / UltiPro"),
    employer_career("bamboohr", "BambooHR"),
    employer_career("jazzhr", "JazzHR"),
    employer_career("recruitee", "Recruitee"),
    employer_career("teamtailor", "Teamtailor"),
    employer_career("pinpoint", "Pinpoint"),
    employer_career("comeet", "Comeet"),
    employer_career("personio", "Personio"),
    employer_career("rippling", "Rippling Recruiting"),
    employer_career("adp", "ADP Recruiting"),
    employer_career("paylocity", "Paylocity"),
    employer_career("dayforce", "Dayforce"),
    employer_career("taleo", "Taleo"),
    employer_career("pageup", "PageUp"),
    employer_career("peopleadmin", "PeopleAdmin"),
    employer_career("cornerstone", "Cornerstone"),
    employer_career(
        "neogov",
        "GovernmentJobs / NEOGOV",
        notes="Detect public government employer job pages; use a dedicated adapter only if a reviewed public interface is available.",
    ),
    partnership(
        "indeed",
        "Indeed",
        official_api=True,
        docs="https://docs.indeed.com/job-sync-api",
        notes=(
            "The documented Job Sync API is an approved-partner/ATS job synchronization product, "
            "not a general anonymous search export for arbitrary crawling."
        ),
    ),
    partnership(
        "linkedin",
        "LinkedIn",
        official_api=True,
        docs="https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview",
        notes="Use approved Talent Solutions / Apply Connect partner access only.",
    ),
    partnership("dice", "Dice"),
    partnership("monster", "Monster"),
    partnership("ziprecruiter", "ZipRecruiter"),
    partnership("glassdoor", "Glassdoor"),
    partnership("careerbuilder", "CareerBuilder"),
    partnership("simplyhired", "SimplyHired", auth=False),
    partnership(
        "wellfound",
        "Wellfound",
        auth=False,
        notes="Startup company discovery may be useful, but job ingestion requires authorized access or employer-origin resolution.",
    ),
    partnership(
        "builtin",
        "Built In",
        auth=False,
        notes="Use company discovery as an input, then prefer employer ATS/career pages.",
    ),
    partnership(
        "higheredjobs",
        "HigherEdJobs",
        auth=False,
        notes="Prefer university-origin ATS/career pages unless an authorized feed is contracted.",
    ),
    partnership("handshake", "Handshake"),
    partnership(
        "idealist",
        "Idealist",
        auth=False,
        notes="Prefer nonprofit employer-origin career pages unless an authorized feed is available.",
    ),
    partnership("devex", "Devex"),
    partnership(
        "uncareers",
        "UN Careers",
        auth=False,
        notes="Prefer official organization job pages and any documented public feed before generic extraction.",
    ),
    partnership(
        "workforgood",
        "Work for Good",
        auth=False,
        notes="Prefer nonprofit employer-origin sources unless a licensed feed is available.",
    ),
)


TRUST_WEIGHTS: dict[str, int] = {
    "APPLYAI_FIRST_PARTY": 100,
    "EMPLOYER_DIRECT": 100,
    "EMPLOYER_OFFICIAL_API": 95,
    "OFFICIAL_ATS": 95,
    "EMPLOYER_JSONLD": 90,
    "STRUCTURED_JOB_PAGE": 90,
    "EMPLOYER_CAREER_SITE": 85,
    "GOVERNMENT_OFFICIAL": 75,
    "AUTHORIZED_AGGREGATOR_FEED": 70,
    "LICENSED_FEED": 70,
    "VERIFIED_PARTNER": 60,
    "THIRD_PARTY_SOURCE": 50,
    "CANDIDATE_IMPORTED": 40,
    "UNVERIFIED_PUBLIC_SOURCE": 20,
    "UNVERIFIED": 20,
}


def trust_weight(trust_level: str) -> int:
    return TRUST_WEIGHTS.get(trust_level, 0)


def capability_metadata(seed: ProviderCapabilitySeed) -> dict:
    return {
        "requires_credentials": seed.authentication_required,
        "requires_partnership": seed.requires_partnership,
        "rate_limit_policy": seed.rate_limit_policy,
        "pagination_strategy": seed.pagination_strategy,
        "supports_delta": seed.supports_delta,
        "supports_closure_detection": seed.supports_closure_detection,
        "trust_level": seed.trust_level,
        "allowed_for_automated_ingestion": seed.allowed_for_automated_ingestion,
        "reason": seed.reason,
    }


def seed_source_capabilities(session: Session) -> list[JobSourceCapability]:
    now = datetime.now(timezone.utc)
    records: list[JobSourceCapability] = []
    for seed in PROVIDER_CAPABILITY_SEEDS:
        record = session.scalar(
            select(JobSourceCapability).where(
                JobSourceCapability.provider_key == seed.provider_key
            )
        )
        seed_metadata = capability_metadata(seed)
        values = {
            "display_name": seed.display_name,
            "access_mode": seed.access_mode.value,
            "implementation_status": seed.implementation_status.value,
            "official_api_available": seed.official_api_available,
            "public_feed_available": seed.public_feed_available,
            "partner_feed_available": seed.partner_feed_available,
            "public_page_access": seed.public_page_access,
            "authentication_required": seed.authentication_required,
            "robots_policy": seed.robots_policy,
            "recommended_strategy": seed.recommended_strategy,
            "documentation_url": seed.documentation_url,
            "notes": seed.notes,
            "metadata_json": seed_metadata,
            "reviewed_at": now,
        }
        if record is None:
            record = JobSourceCapability(provider_key=seed.provider_key, **values)
            session.add(record)
        else:
            existing_metadata = dict(record.metadata_json or {})
            if existing_metadata.get("operator_override"):
                # Keep operator-reviewed policy/status decisions durable while still refreshing
                # non-policy provider facts and filling metadata fields introduced by new code.
                record.display_name = seed.display_name
                record.official_api_available = seed.official_api_available
                record.public_feed_available = seed.public_feed_available
                record.partner_feed_available = seed.partner_feed_available
                record.public_page_access = seed.public_page_access
                record.documentation_url = seed.documentation_url
                for key, value in seed_metadata.items():
                    existing_metadata.setdefault(key, value)
                record.metadata_json = existing_metadata
            else:
                for key, value in values.items():
                    setattr(record, key, value)
        records.append(record)
    session.flush()
    return records
