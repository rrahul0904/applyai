from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/interview-intelligence/execution", tags=["interview execution"])

LANGUAGE_ALIASES = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "cpp": "c++",
    "c++": "c++",
    "go": "go",
}


class ExecuteWrite(BaseModel):
    language: Literal["python", "javascript", "typescript", "java", "cpp", "c++", "go"]
    code: str = Field(min_length=1, max_length=60_000)
    stdin: str = Field(default="", max_length=20_000)


def _provider() -> str:
    return os.getenv("INTERVIEW_EXECUTION_PROVIDER", "disabled").strip().lower()


def _piston_url() -> str | None:
    value = os.getenv("INTERVIEW_PISTON_URL", "").strip().rstrip("/")
    return value or None


@router.get("/capability")
def execution_capability(_user: User = Depends(get_current_user)) -> dict[str, Any]:
    configured = _provider() == "piston" and bool(_piston_url())
    return {
        "configured": configured,
        "provider": "piston" if configured else "disabled",
        "languages": sorted(LANGUAGE_ALIASES),
        "sql_execution": False,
        "trust_boundary": "remote-isolated-sandbox",
    }


@router.post("/run")
def run_code(payload: ExecuteWrite, _user: User = Depends(get_current_user)) -> dict[str, Any]:
    if _provider() != "piston" or not _piston_url():
        raise HTTPException(status_code=503, detail="Interview code execution sandbox is not configured")

    headers: dict[str, str] = {"content-type": "application/json"}
    token = os.getenv("INTERVIEW_PISTON_TOKEN", "").strip()
    if token:
        headers["authorization"] = f"Bearer {token}"

    body = {
        "language": LANGUAGE_ALIASES[payload.language],
        "version": "*",
        "files": [{"name": "main", "content": payload.code}],
        "stdin": payload.stdin,
        "compile_timeout": 5000,
        "run_timeout": 5000,
        "compile_memory_limit": 256_000_000,
        "run_memory_limit": 256_000_000,
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(f"{_piston_url()}/api/v2/execute", headers=headers, json=body)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Interview execution sandbox is unavailable") from exc

    raw = response.json()
    compile_result = raw.get("compile") or {}
    run_result = raw.get("run") or {}
    stdout = str(run_result.get("stdout") or "")[:50_000]
    stderr = str(run_result.get("stderr") or compile_result.get("stderr") or "")[:50_000]
    code = run_result.get("code")
    signal = run_result.get("signal")
    return {
        "provider": "piston",
        "language": payload.language,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": code,
        "signal": signal,
        "status": "PASSED" if code == 0 and not signal else "FAILED",
        "sandboxed": True,
    }
