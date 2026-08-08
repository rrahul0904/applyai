from __future__ import annotations

import os

import httpx

from app.job_source_models import JobSourceRegistry
from app.jobs.adapters import JobSourceAdapterFactory
from app.jobs.connectors import JobSourceConnector
from app.jobs.contracts import JobSourceType, SourceTrustLevel
from app.jobs.generic_career import CareerSiteJobConnector
from app.jobs.partner_feed import PartnerFeedConnector
from app.jobs.public_feeds import ReliefWebJobsConnector, USAJobsConnector
from app.jobs.smartrecruiters import SmartRecruitersPostingConnector


def _smartrecruiters_adapter(
    source: JobSourceRegistry,
    configuration: dict,
    *,
    client: httpx.Client | None,
) -> SmartRecruitersPostingConnector:
    identity = str(configuration.get("company_identifier") or source.source_identity).strip()
    if identity.startswith("SMARTRECRUITERS:"):
        identity = identity.split(":", 1)[1]
    return SmartRecruitersPostingConnector(
        identity,
        page_size=int(configuration.get("page_size") or 100),
        max_pages=int(configuration.get("max_pages") or 20),
        max_jobs=int(configuration.get("max_jobs") or 2000),
        request_interval_seconds=float(configuration.get("request_interval_seconds") or 0.11),
        client=client,
    )


def _partner_feed_adapter(
    source: JobSourceRegistry,
    configuration: dict,
    source_type: JobSourceType,
) -> PartnerFeedConnector:
    feed_url = str(configuration.get("feed_url") or source.base_url or "").strip()
    if not feed_url:
        raise ValueError("Authorized/licensed feed source requires feed_url or base_url")
    default_format = {
        JobSourceType.JSON_FEED: "json",
        JobSourceType.XML_FEED: "xml",
    }.get(source_type, "json")
    trust_value = str(
        configuration.get("trust_level")
        or source.trust_level
        or SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED.value
    )
    try:
        trust_level = SourceTrustLevel(trust_value)
    except ValueError:
        trust_level = SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED
    field_map = configuration.get("field_map")
    if field_map is not None and not isinstance(field_map, dict):
        raise ValueError("Authorized feed field_map must be an object")
    return PartnerFeedConnector(
        feed_url=feed_url,
        source_identity=str(configuration.get("source_identity") or source.source_identity),
        provider_key=str(configuration.get("provider_key") or source.source_identity),
        feed_format=str(configuration.get("feed_format") or default_format),
        field_map=field_map,
        source_type=source_type,
        trust_level=trust_level,
        authoritative_snapshot=bool(configuration.get("authoritative_snapshot", False)),
        max_response_bytes=int(configuration.get("max_response_bytes") or 20 * 1024 * 1024),
        timeout_seconds=float(configuration.get("timeout_seconds") or 30),
    )


def create_source_adapter(
    source: JobSourceRegistry,
    *,
    client: httpx.Client | None = None,
) -> JobSourceConnector:
    source_type = JobSourceType(source.source_type)
    configuration = dict(source.configuration or {})

    if source_type == JobSourceType.USAJOBS:
        api_key = str(configuration.get("api_key") or "").strip() or None
        user_agent = str(configuration.get("user_agent") or "").strip() or None
        if not api_key:
            env_name = str(configuration.get("api_key_env") or "USAJOBS_API_KEY")
            api_key = os.getenv(env_name)
        if not user_agent:
            env_name = str(configuration.get("user_agent_env") or "USAJOBS_USER_AGENT")
            user_agent = os.getenv(env_name)
        return USAJobsConnector(
            api_key=api_key,
            user_agent=user_agent,
            results_per_page=int(configuration.get("results_per_page") or 500),
            max_pages=int(configuration.get("max_pages") or 20),
            client=client,
        )

    if source_type == JobSourceType.RELIEFWEB:
        appname = str(configuration.get("appname") or "").strip() or None
        if not appname:
            env_name = str(configuration.get("appname_env") or "RELIEFWEB_APPNAME")
            appname = os.getenv(env_name)
        return ReliefWebJobsConnector(
            appname=appname,
            page_size=int(configuration.get("page_size") or 1000),
            max_pages=int(configuration.get("max_pages") or 20),
            client=client,
        )

    if source_type == JobSourceType.SMARTRECRUITERS:
        return _smartrecruiters_adapter(source, configuration, client=client)

    if source_type in {
        JobSourceType.AUTHORIZED_AGGREGATOR_FEED,
        JobSourceType.JSON_FEED,
        JobSourceType.XML_FEED,
    }:
        return _partner_feed_adapter(source, configuration, source_type)

    if source_type == JobSourceType.CAREER_SITE:
        if str(configuration.get("detected_provider") or "").upper() == JobSourceType.SMARTRECRUITERS.value:
            return _smartrecruiters_adapter(source, configuration, client=client)
        careers_url = str(
            configuration.get("careers_url")
            or source.careers_url
            or source.base_url
            or ""
        ).strip()
        if not careers_url:
            raise ValueError("CAREER_SITE source requires careers_url or base_url")
        return CareerSiteJobConnector(
            careers_url,
            source_identity=source.source_identity,
            max_pages=int(configuration.get("max_pages") or 60),
            max_jobs=int(configuration.get("max_jobs") or 50),
            max_response_bytes=int(
                configuration.get("max_response_bytes") or 2 * 1024 * 1024
            ),
            max_redirects=int(configuration.get("max_redirects") or 4),
            timeout_seconds=float(configuration.get("timeout_seconds") or 12),
        )

    return JobSourceAdapterFactory.create(source, client=client)
