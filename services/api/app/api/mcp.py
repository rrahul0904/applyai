from __future__ import annotations

import json
import uuid
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents.tools.registry import application_read, candidate_profile_read, resume_master_read
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import Application, ApplicationEvent, Company, Job, JobLocation, User


router = APIRouter(prefix="/mcp", tags=["mcp"])

MCP_PROTOCOL_VERSION = "2026-07-28"
SERVER_NAME = "applyai-candidate"
SERVER_VERSION = "0.1.0"


def _schema(properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


MCP_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "get_platform_context",
        "title": "Get ApplyAI candidate context",
        "description": (
            "Return the authenticated candidate's profile, resume readiness, pipeline summary, "
            "and the approval boundary external agents must respect."
        ),
        "inputSchema": _schema(),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "search_jobs",
        "title": "Search active ApplyAI jobs",
        "description": "Search active listings by text, location, and work mode.",
        "inputSchema": _schema(
            {
                "query": {"type": "string", "maxLength": 240},
                "location": {"type": "string", "maxLength": 240},
                "work_mode": {"type": "string", "maxLength": 48},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
            }
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "browse_listings",
        "title": "Browse active ApplyAI listings",
        "description": "Browse the newest active listings, optionally filtered by location and work mode.",
        "inputSchema": _schema(
            {
                "location": {"type": "string", "maxLength": 240},
                "work_mode": {"type": "string", "maxLength": 48},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
            }
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "add_listing_to_pipeline",
        "title": "Add listing to candidate pipeline",
        "description": (
            "Idempotently stage an active listing in the authenticated candidate's application pipeline. "
            "This does not submit an application."
        ),
        "inputSchema": _schema(
            {"job_id": {"type": "string", "format": "uuid"}},
            required=["job_id"],
        ),
        "annotations": {"destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "apply_to_job",
        "title": "Prepare an application for approval",
        "description": (
            "Stage the listing and return the existing ApplyAI human-approval boundary. "
            "The MCP endpoint never submits to an employer or marks an application APPLIED."
        ),
        "inputSchema": _schema(
            {"job_id": {"type": "string", "format": "uuid"}},
            required=["job_id"],
        ),
        "annotations": {"destructiveHint": False, "idempotentHint": True},
    },
)


def _protocol_error(request_id: Any, code: int, message: str, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}},
    )


def _complete(data: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": json.dumps(data, default=str, sort_keys=True)}],
        "structuredContent": data,
        "isError": is_error,
    }


def _tool_error(message: str, *, code: str = "TOOL_ERROR") -> dict[str, Any]:
    return _complete({"code": code, "message": message}, is_error=True)


def _parse_uuid(value: Any, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid UUID") from exc


def _bounded_limit(value: Any) -> int:
    if value is None:
        return 10
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    if limit < 1 or limit > 25:
        raise ValueError("limit must be between 1 and 25")
    return limit


def _listing_payload(session: Session, job: Job, company: Company) -> dict[str, Any]:
    locations = list(
        session.scalars(
            select(JobLocation).where(JobLocation.job_id == job.id).order_by(JobLocation.id)
        )
    )
    return {
        "id": str(job.id),
        "title": job.title,
        "company": company.canonical_name,
        "employment_type": job.employment_type,
        "seniority": job.seniority,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "last_seen_at": job.last_seen_at.isoformat() if job.last_seen_at else None,
        "data_origin": job.data_origin,
        "locations": [
            {
                "text": row.location_text,
                "city": row.city,
                "region": row.region,
                "country_code": row.country_code,
                "work_mode": row.work_mode,
            }
            for row in locations
        ],
    }


def _browse_jobs(session: Session, arguments: dict[str, Any], *, allow_query: bool) -> dict[str, Any]:
    limit = _bounded_limit(arguments.get("limit"))
    location = str(arguments.get("location") or "").strip()
    work_mode = str(arguments.get("work_mode") or "").strip().upper()
    query_text = str(arguments.get("query") or "").strip() if allow_query else ""

    statement = select(Job, Company).join(Company, Company.id == Job.company_id).where(Job.status == "ACTIVE")
    if query_text:
        pattern = f"%{query_text}%"
        statement = statement.where(
            or_(
                Job.title.ilike(pattern),
                Company.canonical_name.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )
    if location:
        location_pattern = f"%{location}%"
        statement = statement.where(
            select(JobLocation.id)
            .where(JobLocation.job_id == Job.id, JobLocation.location_text.ilike(location_pattern))
            .exists()
        )
    if work_mode:
        statement = statement.where(
            select(JobLocation.id)
            .where(JobLocation.job_id == Job.id, JobLocation.work_mode == work_mode)
            .exists()
        )

    rows = list(
        session.execute(
            statement.order_by(Job.posted_at.desc().nullslast(), Job.last_seen_at.desc(), Job.id).limit(limit)
        )
    )
    return {
        "listings": [_listing_payload(session, job, company) for job, company in rows],
        "returned": len(rows),
        "filters": {
            "query": query_text or None,
            "location": location or None,
            "work_mode": work_mode or None,
        },
    }


def _ensure_pipeline_application(session: Session, user: User, job_id: uuid.UUID, *, intent: str) -> tuple[Application, bool]:
    job = session.get(Job, job_id)
    if job is None:
        raise LookupError("Job not found")
    if job.status != "ACTIVE":
        raise ValueError("Job is not active")

    application = session.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job.id)
    )
    if application is not None:
        return application, False

    application = Application(user_id=user.id, job_id=job.id, current_status="PREPARING")
    session.add(application)
    session.flush()
    session.add(
        ApplicationEvent(
            application_id=application.id,
            actor_user_id=user.id,
            from_status=None,
            to_status="PREPARING",
            metadata_json={"source": "mcp", "intent": intent},
        )
    )
    session.commit()
    session.refresh(application)
    return application, True


def _platform_context(session: Session, user: User) -> dict[str, Any]:
    profile = candidate_profile_read(session, user.id, {})
    resume = resume_master_read(session, user.id, {})
    applications = application_read(session, user.id, {}).get("applications", [])
    status_counts = Counter(str(row.get("current_status") or "UNKNOWN") for row in applications)
    return {
        "candidate": profile,
        "resume": {
            "resume_id": resume.get("resume_id"),
            "version_id": resume.get("version_id"),
            "version_number": resume.get("version_number"),
            "ready": bool(resume.get("version_id")),
        },
        "pipeline": {"total": len(applications), "status_counts": dict(sorted(status_counts.items()))},
        "guardrails": {
            "employer_submission_requires_applyai_approval": True,
            "mcp_can_mark_applied": False,
            "mcp_can_bypass_external_auth_or_captcha": False,
        },
    }


def _call_tool(name: str, arguments: dict[str, Any], session: Session, user: User) -> dict[str, Any]:
    try:
        if name == "get_platform_context":
            return _complete(_platform_context(session, user))
        if name == "search_jobs":
            return _complete(_browse_jobs(session, arguments, allow_query=True))
        if name == "browse_listings":
            return _complete(_browse_jobs(session, arguments, allow_query=False))
        if name == "add_listing_to_pipeline":
            job_id = _parse_uuid(arguments.get("job_id"), "job_id")
            application, created = _ensure_pipeline_application(
                session, user, job_id, intent="add_listing_to_pipeline"
            )
            return _complete(
                {
                    "application_id": str(application.id),
                    "job_id": str(application.job_id),
                    "status": application.current_status,
                    "created": created,
                    "submitted": False,
                }
            )
        if name == "apply_to_job":
            job_id = _parse_uuid(arguments.get("job_id"), "job_id")
            application, created = _ensure_pipeline_application(session, user, job_id, intent="apply_to_job")
            return _complete(
                {
                    "application_id": str(application.id),
                    "job_id": str(application.job_id),
                    "status": "approval_required",
                    "pipeline_status": application.current_status,
                    "created": created,
                    "submission_attempted": False,
                    "next_action": (
                        "Review the prepared application in ApplyAI and use the existing candidate approval "
                        "and submission workflow."
                    ),
                }
            )
    except LookupError as exc:
        return _tool_error(str(exc), code="NOT_FOUND")
    except ValueError as exc:
        return _tool_error(str(exc), code="INVALID_ARGUMENT")

    return _tool_error(f"Unknown tool: {name}", code="UNKNOWN_TOOL")


@router.post("")
def mcp(
    body: dict[str, Any],
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    request_id = body.get("id")
    if body.get("jsonrpc") != "2.0" or not isinstance(body.get("method"), str):
        return _protocol_error(request_id, -32600, "Invalid Request", status_code=400)

    method = str(body["method"])
    params = body.get("params") or {}
    if not isinstance(params, dict):
        return _protocol_error(request_id, -32602, "Invalid params", status_code=400)

    protocol_header = request.headers.get("MCP-Protocol-Version")
    method_header = request.headers.get("Mcp-Method")
    if protocol_header != MCP_PROTOCOL_VERSION:
        return _protocol_error(
            request_id,
            -32001,
            f"Unsupported MCP protocol version; expected {MCP_PROTOCOL_VERSION}",
            status_code=400,
        )
    if method_header != method:
        return _protocol_error(request_id, -32020, "Mcp-Method header does not match JSON-RPC method", status_code=400)

    meta = params.get("_meta") or {}
    if not isinstance(meta, dict):
        return _protocol_error(request_id, -32602, "params._meta must be an object", status_code=400)
    meta_version = meta.get("io.modelcontextprotocol/protocolVersion")
    if meta_version not in (None, MCP_PROTOCOL_VERSION):
        return _protocol_error(request_id, -32001, "Request metadata protocol version does not match", status_code=400)

    if method == "server/discover":
        result = {
            "resultType": "complete",
            "supportedVersions": [MCP_PROTOCOL_VERSION],
            "capabilities": {"tools": {"listChanged": False}},
            "_meta": {
                "io.modelcontextprotocol/serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}
            },
            "instructions": (
                "Use search_jobs or browse_listings to discover active roles. Stage a role with "
                "add_listing_to_pipeline. apply_to_job only prepares the existing ApplyAI approval boundary "
                "and never submits directly."
            ),
            "ttlMs": 60000,
            "cacheScope": "private",
        }
        return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": result})

    if method == "tools/list":
        result = {
            "resultType": "complete",
            "tools": list(MCP_TOOLS),
            "ttlMs": 60000,
            "cacheScope": "private",
        }
        return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": result})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _protocol_error(request_id, -32602, "tools/call requires name and object arguments", status_code=400)
        if request.headers.get("Mcp-Name") != name:
            return _protocol_error(request_id, -32020, "Mcp-Name header does not match tool name", status_code=400)
        known_names = {tool["name"] for tool in MCP_TOOLS}
        if name not in known_names:
            return _protocol_error(request_id, -32602, f"Unknown tool: {name}")
        result = _call_tool(name, arguments, session, user)
        return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": result})

    return _protocol_error(request_id, -32601, f"Method not found: {method}")
