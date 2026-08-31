export type ResumeShareSession = {
  viewer: string;
  session_key: string;
  first_seen_at: string;
  last_seen_at: string;
  interest_score: number;
  intent: "BROWSED" | "ENGAGED" | "DEEP_READ";
  views: number;
  dwell_ms: number;
  scroll_depth: number;
  downloads: number;
  link_clicks: number;
  copies: number;
};

export type ResumeShareTimelineEvent = {
  viewer: string;
  event_type: string;
  value: number | null;
  target: string | null;
  occurred_at: string;
};

export type ResumeShareSnapshot = {
  id: string;
  public_token: string;
  public_path: string;
  label: string;
  channel: string | null;
  status: string;
  active: boolean;
  always_current: boolean;
  allow_download: boolean;
  expires_at: string | null;
  application_id: string | null;
  resume_version_id: string | null;
  filename: string | null;
  created_at: string;
  updated_at: string;
  job_id: string | null;
  job_title: string | null;
  company_name: string | null;
  analytics: {
    views: number;
    unique_viewers: number;
    returning_viewers: number;
    downloads: number;
    link_clicks: number;
    copies: number;
    average_interest_score: number;
    suspected_bot_events: number;
    sessions: ResumeShareSession[];
    timeline: ResumeShareTimelineEvent[];
  };
  privacy: {
    raw_ip_stored: boolean;
    cross_link_fingerprinting: boolean;
    company_identity_inferred: boolean;
    engagement_is_hiring_probability: boolean;
  };
};

export type ResumeShareCreate = {
  resume_version_id?: string | null;
  job_id?: string | null;
  application_id?: string | null;
  label?: string | null;
  channel?: string | null;
  always_current?: boolean;
  allow_download?: boolean;
  expires_at?: string | null;
};

export type ResumeShareUpdate = {
  label?: string;
  channel?: string | null;
  allow_download?: boolean;
  expires_at?: string | null;
  status?: "ACTIVE" | "REVOKED";
};

export class ResumeShareError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ResumeShareError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}) {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: { message?: string } }
      | null;
    throw new ResumeShareError(
      response.status,
      payload?.error?.message ?? "We could not update Resume Share Intelligence.",
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const resumeShareApi = {
  list: (signal?: AbortSignal) =>
    request<ResumeShareSnapshot[]>("/resume-shares", { signal }),
  create: (payload: ResumeShareCreate) =>
    request<ResumeShareSnapshot>("/resume-shares", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: ResumeShareUpdate) =>
    request<ResumeShareSnapshot>(`/resume-shares/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  remove: (id: string) =>
    request<void>(`/resume-shares/${id}`, { method: "DELETE" }),
};
