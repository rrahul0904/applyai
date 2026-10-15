from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.clerk_instance import clerk_instance_fingerprint
from app.core.config import Settings
from app.core.supabase_instance import supabase_instance_fingerprint


class APIReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    database_reachable: bool
    database_migrations_current: bool
    storage_configured: bool
    storage_reachable: bool
    auth_provider: Literal["clerk", "supabase", "dev-test", "unknown"]
    auth_configured: bool
    auth_instance_match: bool
    operator_auth_configured: bool
    operator_auth_location: Literal["database", "api", ""]
    task_queue_configured: bool
    background_worker_configured: bool
    background_worker_healthy: bool
    deployment_sha: str
    clerk_instance_fingerprint: str
    supabase_project_fingerprint: str


def deployment_sha() -> str:
    for name in (
        "VERCEL_GIT_COMMIT_SHA",
        "RAILWAY_GIT_COMMIT_SHA",
        "GITHUB_SHA",
        "GIT_SHA",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value[:64]
    return ""


def build_readiness_response(
    settings: Settings,
    *,
    database_reachable: bool,
    database_migrations_current: bool,
    storage_reachable: bool,
    operator_auth_configured: bool,
    task_queue_configured: bool,
    background_worker_healthy: bool,
    deployed_sha: str | None = None,
) -> APIReadiness:
    provider = settings.auth_provider
    supabase_fingerprint = supabase_instance_fingerprint(settings.supabase_url)
    clerk_fingerprint = clerk_instance_fingerprint(settings.clerk_issuer)
    if provider == "supabase":
        auth_configured = bool(
            settings.supabase_url
            and settings.resolved_supabase_project_ref
            and settings.resolved_supabase_jwks_url
        )
        auth_instance_match = bool(auth_configured and supabase_fingerprint)
        auth_fingerprint = supabase_fingerprint
    elif provider == "clerk":
        auth_configured = bool(settings.clerk_issuer and settings.clerk_jwks_url)
        auth_instance_match = bool(auth_configured and clerk_fingerprint)
        auth_fingerprint = clerk_fingerprint
    else:
        auth_configured = False
        auth_instance_match = False
        auth_fingerprint = ""

    configured_storage = settings.storage_runtime_configured
    configured_worker = settings.background_worker_configured
    sha = (deployed_sha if deployed_sha is not None else deployment_sha()).strip()
    checks_pass = all(
        (
            database_reachable,
            database_migrations_current,
            configured_storage,
            storage_reachable,
            auth_configured,
            auth_instance_match,
            operator_auth_configured,
            task_queue_configured,
            configured_worker,
            background_worker_healthy,
            bool(sha),
        )
    )

    return APIReadiness(
        status="ready" if checks_pass else "not_ready",
        database_reachable=database_reachable,
        database_migrations_current=database_migrations_current,
        storage_configured=configured_storage,
        storage_reachable=storage_reachable,
        auth_provider=provider if provider in {"clerk", "supabase", "dev-test"} else "unknown",
        auth_configured=auth_configured,
        auth_instance_match=auth_instance_match,
        operator_auth_configured=operator_auth_configured,
        operator_auth_location=(
            "database" if provider == "supabase" else "api" if provider == "clerk" else ""
        ),
        task_queue_configured=task_queue_configured,
        background_worker_configured=configured_worker,
        background_worker_healthy=background_worker_healthy,
        deployment_sha=sha,
        clerk_instance_fingerprint=clerk_fingerprint,
        supabase_project_fingerprint=supabase_fingerprint,
    )
