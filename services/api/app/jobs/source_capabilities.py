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
    PUBLIC_ATS = "PUBLIC_ATS"
    PUBLIC_STRUCTURED_PAGE = "PUBLIC_STRUCTURED_PAGE"
    EMPLOYER_CAREER_SITE = "EMPLOYER_CAREER_SITE"
    FIRST_PARTY_APPLYAI = "FIRST_PARTY_APPLYAI"
    PARTNERSHIP_REQUIRED = "PARTNERSHIP_REQUIRED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    UNSUPPORTED = "UNSUPPORTED"


class ProviderImplementationStatus(StrEnum):
    SOURCE_IMPLEMENTED = "SOURCE_IMPLEMENTED"
    LIVE_PUBLIC_SOURCE_VERIFIED = "LIVE_PUBLIC_SOURCE_VERIFIED"
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
    robots_policy: str = "SOURCE_SPECIFIC"
    recommended_strategy: str = ""
    documentation_url: str | None = None
    notes: str | None = None


# Conservative catalog. It is intentionally permissible to under-claim access. A provider
# classified as partnership-required must not be turned into a crawler merely because pages
# happen to be fetchable from a developer laptop.
PROVIDER_CAPABILITY_SEEDS: tuple[ProviderCapabilitySeed, ...] = (
    ProviderCapabilitySeed(
        "applyai",
        "ApplyAI first-party employers",
        SourceAccessMode.FIRST_PARTY_APPLYAI,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        recommended_strategy="Use ApplyAI employer-published jobs as canonical highest-authority observations.",
    ),
    ProviderCapabilitySeed(
        "greenhouse",
        "Greenhouse",
        SourceAccessMode.PUBLIC_ATS,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        official_api_available=True,
        public_page_access=True,
        recommended_strategy="Use the documented public Job Board API for published employer jobs.",
        documentation_url="https://developers.greenhouse.io/job-board.html",
    ),
    ProviderCapabilitySeed(
        "lever",
        "Lever",
        SourceAccessMode.PUBLIC_ATS,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        official_api_available=True,
        public_page_access=True,
        recommended_strategy="Use the public postings API for employer sites; do not automate private recruiting APIs.",
        documentation_url="https://github.com/lever/postings-api",
    ),
    ProviderCapabilitySeed(
        "ashby",
        "Ashby",
        SourceAccessMode.PUBLIC_ATS,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        official_api_available=True,
        public_page_access=True,
        recommended_strategy="Use Ashby's public job-board posting endpoint for published jobs.",
        documentation_url="https://developers.ashbyhq.com/docs/public-job-posting-api",
    ),
    ProviderCapabilitySeed(
        "usajobs",
        "USAJOBS",
        SourceAccessMode.DIRECT_PUBLIC_API,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        official_api_available=True,
        authentication_required=True,
        recommended_strategy="Use the official Search API with an issued API key and configured user agent.",
        documentation_url="https://developer.usajobs.gov/api-reference/get-api-search",
    ),
    ProviderCapabilitySeed(
        "reliefweb",
        "ReliefWeb",
        SourceAccessMode.DIRECT_PUBLIC_API,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        official_api_available=True,
        authentication_required=True,
        recommended_strategy="Use the official ReliefWeb v2 jobs API with a pre-approved appname and quota-aware paging.",
        documentation_url="https://apidoc.reliefweb.int/",
    ),
    ProviderCapabilitySeed(
        "workday",
        "Workday",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        public_page_access=True,
        recommended_strategy="Discover employer Workday career sites and use bounded public structured-page extraction; no private tenant APIs.",
    ),
    ProviderCapabilitySeed(
        "smartrecruiters",
        "SmartRecruiters",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        public_page_access=True,
        recommended_strategy="Prefer employer public career pages / documented public endpoints when available.",
    ),
    ProviderCapabilitySeed(
        "workable",
        "Workable",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        public_page_access=True,
        recommended_strategy="Prefer public employer career pages and structured job data.",
    ),
    ProviderCapabilitySeed(
        "icims",
        "iCIMS",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        public_page_access=True,
        recommended_strategy="Use bounded employer career-site discovery and structured job pages where access permits.",
    ),
    ProviderCapabilitySeed(
        "oracle",
        "Oracle Recruiting / Taleo",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        public_page_access=True,
        recommended_strategy="Use employer public career pages and JSON-LD/HTML extraction; do not use authenticated HCM APIs without authorization.",
    ),
    ProviderCapabilitySeed(
        "successfactors",
        "SAP SuccessFactors",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        public_page_access=True,
        recommended_strategy="Use bounded public career pages when permitted; partner APIs require explicit authorization.",
    ),
    ProviderCapabilitySeed(
        "jobvite",
        "Jobvite",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.NOT_YET_SUPPORTED,
        public_page_access=True,
        recommended_strategy="Use employer-origin career pages after access-policy verification until a dedicated public adapter is justified.",
    ),
    ProviderCapabilitySeed(
        "ukg",
        "UKG",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.NOT_YET_SUPPORTED,
        public_page_access=True,
        recommended_strategy="Use employer-origin public career pages only after access-policy verification.",
    ),
    ProviderCapabilitySeed(
        "pageup",
        "PageUp",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.NOT_YET_SUPPORTED,
        public_page_access=True,
        recommended_strategy="Use public university/employer job pages via the generic structured career-site path.",
    ),
    ProviderCapabilitySeed(
        "peopleadmin",
        "PeopleAdmin",
        SourceAccessMode.EMPLOYER_CAREER_SITE,
        ProviderImplementationStatus.NOT_YET_SUPPORTED,
        public_page_access=True,
        recommended_strategy="Use public institution job pages via the generic structured career-site path.",
    ),
    ProviderCapabilitySeed(
        "indeed",
        "Indeed",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        official_api_available=True,
        partner_feed_available=True,
        authentication_required=True,
        recommended_strategy="Use an authorized Indeed partner integration/feed if approved; otherwise source the original employer ATS/career page.",
        documentation_url="https://docs.indeed.com/job-sync-api",
        notes="The documented Job Sync API is for posting/managing jobs in approved partner contexts, not a general public job-search export for arbitrary crawling.",
    ),
    ProviderCapabilitySeed(
        "linkedin",
        "LinkedIn",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        official_api_available=True,
        partner_feed_available=True,
        authentication_required=True,
        recommended_strategy="Use approved LinkedIn Talent Solutions / Apply Connect partner access only; otherwise resolve jobs to employer-origin sources.",
        documentation_url="https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview",
    ),
    ProviderCapabilitySeed(
        "dice",
        "Dice",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        partner_feed_available=True,
        authentication_required=True,
        recommended_strategy="Pursue a licensed/partner feed; do not make public-page crawling a dependency without explicit permission.",
    ),
    ProviderCapabilitySeed(
        "monster",
        "Monster",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        partner_feed_available=True,
        authentication_required=True,
        recommended_strategy="Pursue an authorized distribution/search feed or resolve jobs to employer-origin sources.",
    ),
    ProviderCapabilitySeed(
        "ziprecruiter",
        "ZipRecruiter",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        partner_feed_available=True,
        authentication_required=True,
        recommended_strategy="Use a contractual/partner integration when available; prefer employer ATS as canonical authority.",
    ),
    ProviderCapabilitySeed(
        "glassdoor",
        "Glassdoor",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        authentication_required=True,
        recommended_strategy="Use licensed access only; prefer original employer jobs for canonical data.",
    ),
    ProviderCapabilitySeed(
        "careerbuilder",
        "CareerBuilder",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        partner_feed_available=True,
        recommended_strategy="Use an authorized feed or partner integration if contracted.",
    ),
    ProviderCapabilitySeed(
        "simplyhired",
        "SimplyHired",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        recommended_strategy="Do not crawl as a default source; prefer employer-origin jobs or a licensed feed.",
    ),
    ProviderCapabilitySeed(
        "wellfound",
        "Wellfound",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        recommended_strategy="Use startup directories for organization discovery only unless explicit job-feed access is authorized.",
    ),
    ProviderCapabilitySeed(
        "builtin",
        "Built In",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        recommended_strategy="Use company discovery as an input, then ingest from employer ATS/career pages unless a licensed feed is available.",
    ),
    ProviderCapabilitySeed(
        "higheredjobs",
        "HigherEdJobs",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        recommended_strategy="Prefer university-origin ATS/career pages; add an authorized feed if a partnership is established.",
    ),
    ProviderCapabilitySeed(
        "handshake",
        "Handshake",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        authentication_required=True,
        recommended_strategy="Use authorized institutional/partner access only; do not automate logged-in job search pages.",
    ),
    ProviderCapabilitySeed(
        "idealist",
        "Idealist",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        recommended_strategy="Prefer nonprofit employer-origin pages unless an authorized feed/API is available.",
    ),
    ProviderCapabilitySeed(
        "devex",
        "Devex",
        SourceAccessMode.PARTNERSHIP_REQUIRED,
        ProviderImplementationStatus.PARTNERSHIP_REQUIRED,
        authentication_required=True,
        recommended_strategy="Use partner/licensed access only; resolve external-apply roles to the original NGO/employer career source when possible.",
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


def seed_source_capabilities(session: Session) -> list[JobSourceCapability]:
    now = datetime.now(timezone.utc)
    records: list[JobSourceCapability] = []
    for seed in PROVIDER_CAPABILITY_SEEDS:
        record = session.scalar(
            select(JobSourceCapability).where(JobSourceCapability.provider_key == seed.provider_key)
        )
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
            "reviewed_at": now,
        }
        if record is None:
            record = JobSourceCapability(provider_key=seed.provider_key, **values)
            session.add(record)
        else:
            for key, value in values.items():
                setattr(record, key, value)
        records.append(record)
    session.flush()
    return records
