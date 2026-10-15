import anyio
import os
from functools import lru_cache
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import (
    agents, application_agent, application_agent_completion_guard, application_agent_documents, application_materials, applications, billing_platform,
    candidate_platform, candidate_workspace, career_intelligence_v2, career_memory, career_prepare, career_product,
    career_product_contract, career_product_polish, career_radar, career_system, company_intelligence, employer_platform,
    internal_agents, internal_ai_evaluation, internal_ai_quality, internal_ai_release_evaluation,
    internal_interview_intelligence_catalog, internal_job_discoveries, internal_job_quality,
    internal_job_sources, internal_job_supply, internal_operations, internal_platform_admin,
    internal_reverse_engineering, internal_worker, interview_execution, interview_intelligence, interview_media, job_imports, job_radar, jobs, mcp, me, onboarding, privacy,
    profiles, referrals, recruiter_lens, resume_shares, resumes, semantic_matching,
)
from app.core.config import get_settings
from app.core.database import engine
from app.core.rate_limit import enforce_rate_limit, request_rate_limit_buckets
from app.core.pulseatlas import dispatch_request_event
from app.core.storage import get_object_storage
from app.readiness import APIReadiness, build_readiness_response
from app.worker_runtime import get_latest_worker_heartbeat
from app.workers.postgres import drain_bounded

settings = get_settings()
app = FastAPI(title="ApplyAI API", version="0.5.0", openapi_url="/api/v1/openapi.json", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_web_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-ApplyAI-Internal-Token",
        "Stripe-Signature",
        "MCP-Protocol-Version",
        "Mcp-Method",
        "Mcp-Name",
    ],
)

@app.middleware("http")
async def request_triggered_tasks(request: Request, call_next):
    response = await call_next(request)
    # Route/status-derived observability only; no request/response body is inspected.
    dispatch_request_event(request.method, request.url.path, response.status_code)
    if settings.request_triggered_tasks_enabled and settings.task_queue_provider == "postgres" and request.method not in {"GET", "HEAD", "OPTIONS"} and response.status_code < 500:
        await anyio.to_thread.run_sync(lambda: drain_bounded(settings, maximum_tasks=settings.request_triggered_task_limit))
    return response

@app.middleware("http")
async def distributed_rate_limit(request: Request, call_next):
    buckets = request_rate_limit_buckets(request, settings)
    decision = None
    if buckets:
        try:
            decision = await anyio.to_thread.run_sync(
                lambda: enforce_rate_limit(
                    engine,
                    buckets,
                    window_seconds=settings.rate_limit_window_seconds,
                )
            )
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "RATE_LIMIT_BACKEND_UNAVAILABLE",
                        "message": "A required service is unavailable",
                    }
                },
            )
        if decision is not None and not decision.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again shortly.",
                    }
                },
                headers={
                    "Retry-After": str(decision.reset_seconds),
                    "RateLimit-Limit": str(decision.limit),
                    "RateLimit-Remaining": "0",
                    "RateLimit-Reset": str(decision.reset_seconds),
                },
            )

    response = await call_next(request)
    if decision is not None:
        response.headers["RateLimit-Limit"] = str(decision.limit)
        response.headers["RateLimit-Remaining"] = str(decision.remaining)
        response.headers["RateLimit-Reset"] = str(decision.reset_seconds)
    return response


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict): detail = exc.detail
    else:
        code_by_status = {401:"AUTH_REQUIRED",403:"FORBIDDEN",404:"NOT_FOUND",409:"CONFLICT",410:"GONE",422:"INVALID_REQUEST",429:"RATE_LIMITED",503:"NOT_READY"}
        detail = {"code": code_by_status.get(exc.status_code, "REQUEST_ERROR"), "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})

@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": ".".join(str(part) for part in error["loc"][1:]), "message": error["msg"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"error":{"code":"VALIDATION_ERROR","message":"Please check the highlighted fields","fields":fields}})

@app.exception_handler(Exception)
async def unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error":{"code":"INTERNAL_ERROR","message":"Something went wrong. Please try again."}})

@app.get("/health")
def health() -> dict[str, str]: return {"status":"ok"}

@lru_cache(maxsize=1)
def _expected_migration_heads() -> frozenset[str]:
    config_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    config = AlembicConfig(str(config_path))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


def _storage_reachable(
    database_reachable: bool,
    database_storage_table_exists: bool,
) -> bool:
    if not settings.storage_runtime_configured:
        return False
    if settings.object_storage_provider == "postgres":
        return database_reachable and database_storage_table_exists
    if settings.object_storage_provider == "local":
        if settings.app_env.lower() in {"staging", "production"}:
            return False
        path = settings.local_storage_path.resolve()
        while not path.exists() and path.parent != path:
            path = path.parent
        return path.is_dir() and os.access(path, os.W_OK)
    try:
        storage = get_object_storage(settings)
        storage.client.head_bucket(Bucket=storage.bucket)  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


@app.get("/ready", response_model=APIReadiness)
def ready() -> JSONResponse:
    database_reachable = False
    database_migrations_current = False
    operator_auth_configured = False
    task_queue_configured = False
    database_storage_table_exists = False
    background_worker_healthy = False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            database_reachable = True
            try:
                applied_heads = frozenset(
                    connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
                )
                database_migrations_current = (
                    bool(applied_heads) and applied_heads == _expected_migration_heads()
                )
            except SQLAlchemyError:
                database_migrations_current = False

            if settings.auth_provider == "supabase":
                operator_auth_configured = bool(
                    connection.scalar(
                        text(
                            "SELECT EXISTS ("
                            "SELECT 1 FROM user_roles ur "
                            "JOIN roles r ON r.id = ur.role_id "
                            "WHERE r.name IN ('operator', 'admin')"
                            ")"
                        )
                    )
                )
            else:
                operator_auth_configured = bool(settings.allowed_operator_emails)
            queue_tables_exist = bool(
                connection.execute(
                    text(
                        "SELECT to_regclass('public.postgres_tasks') IS NOT NULL "
                        "AND to_regclass('public.task_outbox') IS NOT NULL"
                    )
                ).scalar()
            )
            task_queue_configured = (
                settings.task_queue_provider == "postgres" and queue_tables_exist
            )
            if settings.object_storage_provider == "postgres":
                database_storage_table_exists = bool(
                    connection.execute(
                        text("SELECT to_regclass('public.database_objects') IS NOT NULL")
                    ).scalar()
                )
    except SQLAlchemyError:
        database_reachable = False
        database_migrations_current = False
        operator_auth_configured = False
        task_queue_configured = False

    if database_reachable and settings.background_worker_configured:
        try:
            heartbeat = get_latest_worker_heartbeat(
                environment=settings.app_env,
                worker_type="combined_worker",
                max_age_seconds=max(90, settings.worker_runtime_heartbeat_seconds * 3),
            )
            background_worker_healthy = heartbeat.healthy
        except SQLAlchemyError:
            # A failed heartbeat query must fail readiness closed without making
            # the liveness endpoint depend on worker metadata.
            background_worker_healthy = False

    storage_reachable = _storage_reachable(
        database_reachable,
        database_storage_table_exists,
    )
    response = build_readiness_response(
        settings,
        database_reachable=database_reachable,
        database_migrations_current=database_migrations_current,
        storage_reachable=storage_reachable,
        operator_auth_configured=operator_auth_configured,
        task_queue_configured=task_queue_configured,
        background_worker_healthy=background_worker_healthy,
    )
    return JSONResponse(
        status_code=200 if response.status == "ready" else 503,
        content=response.model_dump(),
        headers={"cache-control": "no-store"},
    )

# Prepare exposes static POST routes such as /career-v2/jobs/{job_id}/skill-analysis.
# Register them before Career Intelligence V2's dynamic /jobs/{job_id}/{task_path}
# route so Starlette resolves the specific product routes first without changing
# or breaking the existing AI task-path contract.
app.include_router(career_prepare.router,prefix="/api/v1",include_in_schema=False)
app.include_router(application_materials.router,prefix="/api/v1",include_in_schema=False)
app.include_router(interview_media.router,prefix="/api/v1",include_in_schema=False)
app.include_router(interview_intelligence.router,prefix="/api/v1",include_in_schema=False)
app.include_router(interview_execution.router,prefix="/api/v1",include_in_schema=False)
app.include_router(mcp.router,prefix="/api/v1",include_in_schema=False)
app.include_router(career_radar.router,prefix="/api/v1",include_in_schema=False)
app.include_router(job_radar.router,prefix="/api/v1",include_in_schema=False)

for router in (me.router,onboarding.router,profiles.router,resumes.router,jobs.router,applications.router,career_memory.router,career_intelligence_v2.router,candidate_platform.router,semantic_matching.router,company_intelligence.router,employer_platform.router,billing_platform.router,privacy.router,referrals.router): app.include_router(router,prefix="/api/v1")
for product_router in (candidate_workspace.router,career_product_contract.router,career_product_polish.router,career_product.router,career_system.router,recruiter_lens.router,resume_shares.router,agents.router,application_agent.router,application_agent_documents.router): app.include_router(product_router,prefix="/api/v1",include_in_schema=False)
app.include_router(job_imports.router,prefix="/api/v1",include_in_schema=False)
for internal_router in (internal_agents.router,application_agent_completion_guard.router,application_agent.internal_router,application_agent_documents.internal_router,internal_job_sources.router,internal_job_discoveries.router,internal_job_quality.router,internal_job_supply.router,internal_ai_quality.router,internal_ai_evaluation.router,internal_ai_release_evaluation.router,internal_reverse_engineering.router,interview_intelligence.internal_router,internal_interview_intelligence_catalog.router,referrals.internal_router,internal_operations.router,internal_platform_admin.router,internal_worker.router): app.include_router(internal_router,prefix="/api/v1",include_in_schema=False)
