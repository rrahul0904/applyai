from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agent_models import AgentRun, AgentToolCall
from app.agents.contracts import AgentDefinition
from app.agents.enums import ExecutionClass
from app.agents.tools.registry import TOOL_REGISTRY


class ToolPermissionError(PermissionError):
    pass


_CLASS_RANK = {
    ExecutionClass.READ.value: 1,
    ExecutionClass.PREPARE.value: 2,
    ExecutionClass.EXECUTE.value: 3,
}


def _audit_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"type": type(value).__name__}
    summary: dict[str, Any] = {"keys": sorted(str(key) for key in value.keys())[:40]}
    for key in ("id", "job_id", "company_id", "artifact_id", "resume_id", "version_id"):
        if key in value and value[key] is not None:
            summary[key] = str(value[key])[:255]
    for key in ("applications", "artifacts", "facts", "experiences", "education", "skills", "requirements", "sources"):
        if isinstance(value.get(key), list):
            summary[f"{key}_count"] = len(value[key])
    return summary


class ToolGateway:
    def __init__(self, session: Session, *, run: AgentRun, definition: AgentDefinition) -> None:
        self.session = session
        self.run = run
        self.definition = definition

    def invoke(self, tool_name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        if tool_name in self.definition.denied_tools or tool_name not in self.definition.allowed_tools:
            raise ToolPermissionError(f"TOOL_NOT_ALLOWED:{tool_name}")
        tool = TOOL_REGISTRY.get(tool_name)
        if tool is None:
            raise ToolPermissionError(f"UNKNOWN_TOOL:{tool_name}")
        agent_rank = _CLASS_RANK[self.definition.execution_class.value]
        tool_rank = _CLASS_RANK[tool.execution_class]
        if tool_rank > agent_rank:
            raise ToolPermissionError(f"EXECUTION_CLASS_DENIED:{tool_name}")

        started = time.perf_counter()
        row = AgentToolCall(
            run_id=self.run.id,
            candidate_id=self.run.candidate_id,
            tool_name=tool.name,
            tool_version=tool.version,
            execution_class=tool.execution_class,
            input_json=_audit_summary(args),
            status="RUNNING",
        )
        self.session.add(row)
        self.session.flush()
        try:
            output = tool.handler(self.session, self.run.candidate_id, args)
            row.output_json = _audit_summary(output)
            row.status = "SUCCEEDED"
            row.latency_ms = round((time.perf_counter() - started) * 1000)
            self.session.flush()
            return output
        except Exception as exc:
            row.status = "FAILED"
            row.error_code = type(exc).__name__[:80]
            row.latency_ms = round((time.perf_counter() - started) * 1000)
            self.session.flush()
            raise

    def assert_candidate_scope(self, candidate_id: uuid.UUID) -> None:
        if candidate_id != self.run.candidate_id:
            raise ToolPermissionError("CROSS_CANDIDATE_ACCESS_DENIED")
