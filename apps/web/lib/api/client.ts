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
export type Profile = components["schemas"]["ProfileResponse"];
export type ProfileWrite = components["schemas"]["ProfileReviewWrite"];
export type ResumeVersion = components["schemas"]["ResumeVersionResponse"];
export type ResumeExtraction = components["schemas"]["ResumeExtractionResponse"];
export type Job = components["schemas"]["JobSummary"];
export type JobDetail = components["schemas"]["JobDetail"];
export type JobPage = components["schemas"]["JobSearchPage"];
export type Application = components["schemas"]["ApplicationResponse"];
export type ApplicationNote = components["schemas"]["ApplicationNoteResponse"];

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
    upload: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return request<ResumeVersion>("/resumes", { method: "POST", body });
    },
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
    list: (signal?: AbortSignal) => request<Job[]>("/jobs/saved", { signal }),
    save: (id: string) =>
      request<void>(`/jobs/${id}/save`, { method: "POST" }),
    unsave: (id: string) =>
      request<void>(`/jobs/${id}/save`, { method: "DELETE" }),
  },
  applications: {
    list: (signal?: AbortSignal) =>
      request<Application[]>("/applications", { signal }),
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
};
