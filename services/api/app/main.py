import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import (
    agents, application_agent, application_agent_documents, applications, billing_platform,
    candidate_platform, candidate_workspace, career_intelligence_v2, career_memory, career_product,
    career_product_contract, career_product_polish, career_system, company_intelligence, employer_platform,
    internal_agents, internal_ai_evaluation, internal_ai_quality, internal_job_discoveries, internal_job_quality,
    internal_job_sources, internal_job_supply, internal_platform_admin, job_imports, jobs, me, onboarding, privacy,
    profiles, recruiter_lens, resume_shares, resumes, semantic_matching,
)
from app.core.config import get_settings
from app.core.database import engine
from app.core.pulseatlas import dispatch_request_event
from app.workers.postgres import drain_bounded

settings = get_settings()
app = FastAPI(title="ApplyAI API", version="0.4.0", openapi_url="/api/v1/openapi.json", docs_url="/api/docs")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_web_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-ApplyAI-Internal-Token", "Stripe-Signature"])

@app.middleware("http")
async def request_triggered_tasks(request: Request, call_next):
    response = await call_next(request)
    # Route/status-derived observability only; no request/response body is inspected.
    dispatch_request_event(request.method, request.url.path, response.status_code)
    if settings.request_triggered_tasks_enabled and settings.task_queue_provider == "postgres" and request.method not in {"GET", "HEAD", "OPTIONS"} and response.status_code < 500:
        await anyio.to_thread.run_sync(lambda: drain_bounded(settings, maximum_tasks=settings.request_triggered_task_limit))
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

@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        with engine.connect() as connection: connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail={"code":"NOT_READY","message":"A required service is unavailable"}) from exc
    return {"status":"ready"}

for router in (me.router,onboarding.router,profiles.router,resumes.router,jobs.router,applications.router,career_memory.router,career_intelligence_v2.router,candidate_platform.router,semantic_matching.router,company_intelligence.router,employer_platform.router,billing_platform.router,privacy.router): app.include_router(router,prefix="/api/v1")
for product_router in (candidate_workspace.router,career_product_contract.router,career_product_polish.router,career_product.router,career_system.router,recruiter_lens.router,resume_shares.router,agents.router,application_agent.router,application_agent_documents.router): app.include_router(product_router,prefix="/api/v1",include_in_schema=False)
app.include_router(job_imports.router,prefix="/api/v1",include_in_schema=False)
for internal_router in (internal_agents.router,application_agent.internal_router,application_agent_documents.internal_router,internal_job_sources.router,internal_job_discoveries.router,internal_job_quality.router,internal_job_supply.router,internal_ai_quality.router,internal_ai_evaluation.router,internal_platform_admin.router): app.include_router(internal_router,prefix="/api/v1",include_in_schema=False)
