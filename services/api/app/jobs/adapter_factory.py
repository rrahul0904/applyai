from __future__ import annotations

import os

import httpx

from app.job_source_models import JobSourceRegistry
from app.jobs.adapters import JobSourceAdapterFactory
from app.jobs.connectors import JobSourceConnector
from app.jobs.contracts import JobSourceType
from app.jobs.public_feeds import ReliefWebJobsConnector, USAJobsConnector


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

    return JobSourceAdapterFactory.create(source, client=client)
