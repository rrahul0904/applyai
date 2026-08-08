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
        recommended_strategy=(
            "Detect the employer ATS and ingest only bounded public job pages through the "
            "robots-aware generic career-site connector unless a dedicated documented public API is available."
        ),
        notes=notes,
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
        recommended_strategy=(
            "Use an authorized/licensed provider integration when contracted; otherwise resolve "
            "the opportunity to the original employer ATS or employer career page. Do not bypass access controls."
        ),
        documentation_url=docs,
        notes=notes,
    )


# This catalog is intentionally conservative: technical discoverability is not permission to crawl.
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
        "smartrecruiters",
        "SmartRecruiters",
        SourceAccessMode.PUBLIC_ATS,
        ProviderImplementationStatus.SOURCE_IMPLEMENTED,
        official_api_available=True,
        public_page_access=True,
        recommended_strategy="Use the public Posting API list/detail endpoints for active public company postings.",
        documentation_url="https://developers.smartrecruiters.com/docs/endpoints",
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
