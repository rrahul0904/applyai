export type ApplicationAgentField = {
  field_id: string;
  label: string;
  canonical_key: string;
  field_type: string;
  required: boolean;
  options: string[];
  value: unknown;
  confidence: number;
  source_kind: string;
  source_ref: string | null;
  evidence_refs: string[];
  sensitive: boolean;
  candidate_verified: boolean;
  requires_review: boolean;
  status: string;
};

export type ApplicationExecution = {
  id: string;
  application_id: string;
  job_id: string;
  attempt_number: number;
  approval_mode: "REVIEW_ALL" | "SMART" | "AUTONOMOUS";
  ats_provider: string;
  target_url: string | null;
  state: string;
  fields: ApplicationAgentField[];
  review_items: Array<Record<string, unknown>>;
  missing_fields: Array<Record<string, unknown>>;
  documents: Record<string, Record<string, unknown>>;
  validation: Record<string, unknown>;
  browser_handoff: Record<string, unknown>;
  confirmation_url: string | null;
  confirmation_text: string | null;
  approved_at: string | null;
  started_at: string | null;
  submitted_at: string | null;
  confirmed_at: string | null;
  error_code: string | null;
  created_at: string;
  updated_at: string;
};

export class ApplicationAgentError extends Error {
  status: number;
  code: string;
  payload: unknown;

  constructor(status: number, code: string, message: string, payload: unknown) {
    super(message);
    this.name = "ApplicationAgentError";
    this.status = status;
    this.code = code;
    this.payload = payload;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init.headers || {}) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { error?: { code?: string; message?: string } } | null;
    throw new ApplicationAgentError(
      response.status,
      payload?.error?.code || "APPLICATION_AGENT_ERROR",
      payload?.error?.message || "We could not complete that application-agent request.",
      payload,
    );
  }
  return response.json() as Promise<T>;
}

export const applicationAgentApi = {
  prepare: (applicationId: string, approvalMode: ApplicationExecution["approval_mode"] = "SMART") =>
    request<ApplicationExecution>(`/application-agent/applications/${applicationId}/prepare`, {
      method: "POST",
      body: JSON.stringify({ approval_mode: approvalMode, observed_fields: [] }),
    }),
  latest: (applicationId: string, signal?: AbortSignal) =>
    request<ApplicationExecution>(`/application-agent/applications/${applicationId}/executions/latest`, { signal }),
  reviewField: (executionId: string, fieldId: string, value: unknown, remember: boolean) =>
    request<ApplicationExecution>(`/application-agent/executions/${executionId}/fields/${encodeURIComponent(fieldId)}`, {
      method: "PATCH",
      body: JSON.stringify({ value, candidate_verified: true, remember }),
    }),
  approve: (executionId: string) =>
    request<ApplicationExecution>(`/application-agent/executions/${executionId}/approve`, { method: "POST" }),
  execute: (executionId: string) =>
    request<ApplicationExecution>(`/application-agent/executions/${executionId}/execute`, { method: "POST" }),
};
