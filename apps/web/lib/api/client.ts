import type { components } from "./schema";

export type ApiErrorShape = {
  code: string;
  message: string;
  fields?: Array<{ field: string; message: string }>;
};

export class ApiError extends Error {
  code: string;
  status: number;
  fields?: ApiErrorShape["fields"];

  constructor(status: number, error: ApiErrorShape) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.status = status;
    this.fields = error.fields;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/backend${path}`, {
      ...init,
      headers:
        init.body instanceof FormData
          ? init.headers
          : { "content-type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError(0, {
      code: "NETWORK_ERROR",
      message: "You appear to be offline. Check your connection and try again.",
    });
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: ApiErrorShape }
      | null;
    const fallback: ApiErrorShape = {
      code: response.status === 401 ? "AUTH_REQUIRED" : "REQUEST_ERROR",
      message:
        response.status === 401
          ? "Your session has expired. Please sign in again."
          : "We could not complete that request.",
    };
    throw new ApiError(response.status, payload?.error ?? fallback);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type User = components["schemas"]["UserResponse"];
export type OnboardingState = components["schemas"]["OnboardingStateResponse"];
export type Profile = components["schemas"]["ProfileResponse"] & {
  target_roles: string[];
  work_modes: string[];
};
export type ProfileWrite = components["schemas"]["ProfileReviewWrite"];
export type ResumeVersion = components["schemas"]["ResumeVersionResponse"];
export type ResumeExtraction = components["schemas"]["ResumeExtractionResponse"];
export type ResumeUploadIntent = components["schemas"]["ResumeUploadIntentResponse"];
export type Job = components["schemas"]["JobSummary"];
export type JobDetail = components["schemas"]["JobDetail"];
export type JobPage = components["schemas"]["JobSearchPage"];
export type Application = components["schemas"]["ApplicationResponse"];
export type ApplicationNote = components["schemas"]["ApplicationNoteResponse"];
export type ApplicationListItem = components["schemas"]["ApplicationListItem"];
export type ApplicationListPage = components["schemas"]["ApplicationListPage"];

export type CareerTaskPath =
  | "deep-match"
  | "resume-tailoring"
  | "application-copilot"
  | "interview-prep";

export type AIJobRun = {
  id: string;
  task_type: string;
  job_id: string | null;
  application_id: string | null;
  status: string;
  provider: string;
  model: string;
  prompt_version: string;
  schema_version: string;
  input_hash: string;
  output: Record<string, unknown> | null;
  evidence_refs: string[];
  attempt_count: number;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  error_code: string | null;
  created_at: string;
  completed_at: string | null;
};

export type AIArtifact = {
  id: string;
  run_id: string;
  job_id: string | null;
  application_id: string | null;
  artifact_type: string;
  status: string;
  version: number;
  content: Record<string, unknown>;
  evidence: Record<string, unknown>;
  candidate_verified: boolean;
  created_at: string;
};

export type CareerMatchV2 = {
  job_id: string;
  deterministic_score: number;
  ai_score: number | null;
  final_score: number;
  fit_band: string;
  decision: string;
  confidence: string;
  engine_version: string;
  factors: Array<Record<string, unknown>>;
  evidence: Record<string, unknown>;
  updated_at: string;
};

export type CareerFactCategory =
  | "ACHIEVEMENT"
  | "PROJECT"
  | "METRIC"
  | "RESPONSIBILITY"
  | "CERTIFICATION"
  | "LEADERSHIP_STORY"
  | "INTERVIEW_FEEDBACK"
  | "CAREER_GOAL";

export type CareerFact = {
  id: string;
  category: CareerFactCategory;
  title: string | null;
  fact_text: string;
  source_kind: string;
  source_ref: string | null;
  provenance: string;
  user_verified: boolean;
  tags: string[];
  occurred_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CareerFactWrite = {
  category: CareerFactCategory;
  title?: string | null;
  fact_text: string;
  tags?: string[];
  occurred_at?: string | null;
};

async function uploadResume(file: File): Promise<ResumeVersion> {
  const intent = await request<ResumeUploadIntent>("/resumes/upload-intents", {
    method: "POST",
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      file_size: file.size,
    }),
  });

  if (intent.upload_mode === "PROXY") {
    const body = new FormData();
    body.append("file", file);
    return request<ResumeVersion>("/resumes", { method: "POST", body });
  }

  if (!intent.upload_url || !intent.resume_version_id) {
    throw new ApiError(500, {
      code: "UPLOAD_INTENT_INVALID",
      message: "The resume upload could not be prepared.",
    });
  }

  let uploadResponse: Response;
  try {
    uploadResponse = await fetch(intent.upload_url, {
      method: "PUT",
      headers: intent.upload_headers,
      body: file,
    });
  } catch {
    throw new ApiError(0, {
      code: "UPLOAD_NETWORK_ERROR",
      message: "The resume upload was interrupted. Please try again.",
    });
  }
  if (!uploadResponse.ok) {
    throw new ApiError(uploadResponse.status, {
      code: "UPLOAD_FAILED",
      message: "The resume could not be uploaded to secure storage.",
    });
  }

  return request<ResumeVersion>(
    `/resumes/versions/${intent.resume_version_id}/upload-complete`,
    { method: "POST" },
  );
}

export const api = {
  auth: {
    me: (signal?: AbortSignal) => request<User>("/me", { signal }),
  },
  onboarding: {
    get: (signal?: AbortSignal) =>
      request<OnboardingState>("/onboarding", { signal }),
    update: (stage: string) =>
      request<OnboardingState>("/onboarding", {
        method: "PUT",
        body: JSON.stringify({ stage }),
      }),
  },
  profile: {
    get: (signal?: AbortSignal) =>
      request<Profile | null>("/profile", { signal }),
    save: (payload: ProfileWrite) =>
      request<Profile>("/profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
  },
  resumes: {
    list: (signal?: AbortSignal) =>
      request<ResumeVersion[]>("/resumes", { signal }),
    upload: uploadResume,
    extraction: (resumeId: string, signal?: AbortSignal) =>
      request<ResumeExtraction>(`/resumes/${resumeId}/extraction`, { signal }),
    confirm: (resumeId: string, payload: ProfileWrite) =>
      request<Profile>(`/resumes/${resumeId}/confirm`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
  jobs: {
    search: (params: URLSearchParams, signal?: AbortSignal) =>
      request<JobPage>(`/jobs?${params.toString()}`, { signal }),
    detail: (id: string, signal?: AbortSignal) =>
      request<JobDetail>(`/jobs/${id}`, { signal }),
  },
  savedJobs: {
    list: (signal?: AbortSignal, cursor?: string) => {
      const params = new URLSearchParams();
      if (cursor) params.set("cursor", cursor);
      const query = params.toString();
      const suffix = query ? `?${query}` : "";
      return request<JobPage>(`/jobs/saved${suffix}`, { signal });
    },
    save: (id: string) =>
      request<void>(`/jobs/${id}/save`, { method: "POST" }),
    unsave: (id: string) =>
      request<void>(`/jobs/${id}/save`, { method: "DELETE" }),
  },
  applications: {
    list: (signal?: AbortSignal, cursor?: string) => {
      const params = new URLSearchParams();
      if (cursor) params.set("cursor", cursor);
      const suffix = params.size ? `?${params.toString()}` : "";
      return request<ApplicationListPage>(`/applications${suffix}`, { signal });
    },
    detail: (id: string, signal?: AbortSignal) =>
      request<Application>(`/applications/${id}`, { signal }),
    create: (jobId: string) =>
      request<Application>("/applications", {
        method: "POST",
        body: JSON.stringify({ job_id: jobId }),
      }),
    updateStatus: (id: string, status: string) =>
      request<Application>(`/applications/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    addNote: (id: string, body: string) =>
      request<ApplicationNote>(`/applications/${id}/notes`, {
        method: "POST",
        body: JSON.stringify({ body }),
      }),
    updateNote: (id: string, noteId: string, body: string) =>
      request<ApplicationNote>(`/applications/${id}/notes/${noteId}`, {
        method: "PUT",
        body: JSON.stringify({ body }),
      }),
    deleteNote: (id: string, noteId: string) =>
      request<void>(`/applications/${id}/notes/${noteId}`, {
        method: "DELETE",
      }),
  },
  careerV2: {
    start: (jobId: string, task: CareerTaskPath) =>
      request<AIJobRun>(`/career-v2/jobs/${jobId}/${task}`, { method: "POST" }),
    run: (runId: string, signal?: AbortSignal) =>
      request<AIJobRun>(`/career-v2/runs/${runId}`, { signal }),
    retry: (runId: string) =>
      request<AIJobRun>(`/career-v2/runs/${runId}/retry`, { method: "POST" }),
    artifacts: (jobId?: string, signal?: AbortSignal) => {
      const params = new URLSearchParams();
      if (jobId) params.set("job_id", jobId);
      const suffix = params.size ? `?${params.toString()}` : "";
      return request<{ items: AIArtifact[] }>(`/career-v2/artifacts${suffix}`, { signal });
    },
    artifact: (artifactId: string, signal?: AbortSignal) =>
      request<AIArtifact>(`/career-v2/artifacts/${artifactId}`, { signal }),
    matches: (signal?: AbortSignal) =>
      request<{ items: CareerMatchV2[] }>("/career-v2/matches", { signal }),
    match: (jobId: string, signal?: AbortSignal) =>
      request<CareerMatchV2>(`/career-v2/matches/${jobId}`, { signal }),
    feedback: (artifactId: string, action: string) =>
      request<{ id: string; artifact_id: string; action: string }>(
        `/career-v2/artifacts/${artifactId}/feedback`,
        { method: "POST", body: JSON.stringify({ action, metadata: {} }) },
      ),
  },
  careerMemory: {
    list: (signal?: AbortSignal) =>
      request<CareerFact[]>("/career-memory", { signal }),
    summary: (signal?: AbortSignal) =>
      request<{ verified_fact_count: number; by_category: Record<string, number> }>(
        "/career-memory/summary",
        { signal },
      ),
    create: (payload: CareerFactWrite) =>
      request<CareerFact>("/career-memory", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    update: (factId: string, payload: Partial<CareerFactWrite> & { user_verified?: boolean }) =>
      request<CareerFact>(`/career-memory/${factId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    remove: (factId: string) =>
      request<void>(`/career-memory/${factId}`, { method: "DELETE" }),
  },
};
