export class PlatformApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "PlatformApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: init.body ? { "content-type": "application/json", ...init.headers } : init.headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
    throw new PlatformApiError(response.status, body?.error?.message ?? "Request failed");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type SemanticMatch = {
  job_id: string;
  semantic_score: number;
  title: string;
  company: string;
  posted_at: string | null;
  explanation: string;
};

export type SavedSearch = {
  id: string;
  name: string;
  query: Record<string, unknown>;
  alerts_enabled: boolean;
  minimum_match_score: number;
};

export type ResumeDocument = {
  id: string;
  job_id: string | null;
  base_resume_version_id: string | null;
  title: string;
  content: Record<string, unknown>;
  status: string;
  version: number;
  updated_at: string;
};

export type ResumeExport = {
  filename: string;
  content: string;
  content_type: string;
  content_encoding?: "base64";
  version: number;
  composition?: {
    page_count?: number;
    page_status: "WITHIN_ONE_PAGE_TARGET" | "OVERFLOW_REQUIRES_REVIEW";
    extractable_text: boolean;
  };
};

export type Contact = {
  id: string;
  name: string;
  company: string | null;
  title: string | null;
  email: string | null;
  linkedin_url: string | null;
  relationship: string | null;
  notes: string | null;
  followup_at: string | null;
};

export type NotificationItem = {
  id: string;
  notification_type: string;
  title: string;
  body: string;
  action_url: string | null;
  read_at: string | null;
  created_at: string;
};

export type JobRadarProfile = {
  id: string;
  target_titles: string[];
  skills: string[];
  years_experience: number | null;
  seniority_preferences: string[];
  preferred_locations: string[];
  remote_policy: "ANY" | "REMOTE" | "HYBRID" | "ONSITE";
  salary_min: number | null;
  salary_currency: string;
};

export type JobRadarScan = {
  id: string;
  status: string;
  jobs_seen: number;
  jobs_after_filter: number;
  jobs_ranked: number;
  error_code: string | null;
  error_detail: string | null;
  ai_reranking: string;
  scheduled_delivery: string;
  external_job_providers: string;
  realtime_streaming: string;
  matches: Array<{
    id: string; job_id: string; application_url: string; deterministic_score: number;
    score_breakdown: Record<string, unknown>; source_evidence: Record<string, unknown>; rank: number;
  }>;
};

export const platformApi = {
  jobRadar: {
    profile: () => request<JobRadarProfile>("/job-radar/profile"),
    saveProfile: (payload: Omit<JobRadarProfile, "id">) => request<JobRadarProfile>("/job-radar/profile", { method: "PUT", body: JSON.stringify(payload) }),
    createScan: () => request<JobRadarScan>("/job-radar/scans", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ max_queries: 5, per_query_limit: 25, top_k: 10 }) }),
    getScan: (id: string) => request<JobRadarScan>(`/job-radar/scans/${id}`),
  },
  semanticMatches: (limit = 25) => request<{ engine: string; items: SemanticMatch[] }>(`/semantic-matches?limit=${limit}`),
  recommendations: (limit = 50) => request<{
    ranking_scope: string;
    profile_ready: boolean;
    items: Array<{
      id: string;
      job_id: string;
      title: string;
      company_name: string;
      location: string | null;
      work_mode: string | null;
      posted_at: string | null;
      last_seen_at: string;
      saved: boolean;
      applied: boolean;
      recently_viewed: boolean;
      match_score: number;
      deterministic_score: number;
      career_v2_score: number | null;
      freshness_adjustment: number;
      summary: string;
      explanation: string;
      strengths: string[];
      gaps: string[];
      skills: string[];
      source_label: string;
      data_origin: string;
    }>;
  }>(`/workspace/recommendations?limit=${limit}`),
  trackAnalyticsEvent: (payload: { event_type: string; entity_type?: string; entity_id?: string; metadata?: Record<string, unknown> }) =>
    request<void>("/analytics/events", { method: "POST", body: JSON.stringify(payload) }),
  savedSearches: {
    list: () => request<SavedSearch[]>("/saved-searches"),
    create: (payload: { name: string; query: Record<string, unknown>; alerts_enabled?: boolean; minimum_match_score?: number }) => request<SavedSearch>("/saved-searches", { method: "POST", body: JSON.stringify(payload) }),
    remove: (id: string) => request<void>(`/saved-searches/${id}`, { method: "DELETE" }),
  },
  notifications: {
    list: () => request<NotificationItem[]>("/notifications"),
    read: (id: string) => request<NotificationItem>(`/notifications/${id}/read`, { method: "POST" }),
    preferences: () => request<Record<string, unknown>>("/notification-preferences"),
    savePreferences: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/notification-preferences", { method: "PUT", body: JSON.stringify(payload) }),
  },
  analytics: () => request<Record<string, unknown>>("/analytics/summary"),
  contacts: {
    list: () => request<Contact[]>("/contacts"),
    create: (payload: Record<string, unknown>) => request<Contact>("/contacts", { method: "POST", body: JSON.stringify(payload) }),
    update: (id: string, payload: Record<string, unknown>) => request<Contact>(`/contacts/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
    remove: (id: string) => request<void>(`/contacts/${id}`, { method: "DELETE" }),
  },
  resumeStudio: {
    list: () => request<ResumeDocument[]>("/resume-studio"),
    create: (payload: Record<string, unknown>) => request<ResumeDocument>("/resume-studio", { method: "POST", body: JSON.stringify(payload) }),
    fromJob: (jobId: string) => request<ResumeDocument>(`/resume-studio/from-job/${jobId}`, { method: "POST" }),
    get: (id: string) => request<ResumeDocument>(`/resume-studio/${id}`),
    update: (id: string, payload: Record<string, unknown>) => request<ResumeDocument>(`/resume-studio/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
    export: (id: string, format: "txt" | "html" | "pdf" = "txt") => request<ResumeExport>(`/resume-studio/${id}/export?format=${format}`),
  },
  interview: {
    list: (jobId?: string) => request<Array<Record<string, unknown>>>(`/interview-practice${jobId ? `?job_id=${jobId}` : ""}`),
    create: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/interview-practice", { method: "POST", body: JSON.stringify(payload) }),
    update: (id: string, payload: Record<string, unknown>) => request<Record<string, unknown>>(`/interview-practice/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  },
  billing: {
    subscription: () => request<Record<string, unknown>>("/billing/subscription"),
    checkout: (plan: "PRO" | "TEAM") => request<{ checkout_url?: string }>("/billing/checkout", { method: "POST", body: JSON.stringify({ plan }) }),
    portal: () => request<{ portal_url: string }>("/billing/portal", { method: "POST" }),
  },
  submissions: {
    list: () => request<Array<Record<string, unknown>>>("/submissions"),
    create: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/submissions", { method: "POST", body: JSON.stringify(payload) }),
    approve: (id: string) => request<Record<string, unknown>>(`/submissions/${id}/approve`, { method: "POST" }),
    execute: (id: string) => request<Record<string, unknown>>(`/submissions/${id}/execute`, { method: "POST" }),
  },
  employer: {
    organizations: () => request<Array<Record<string, unknown>>>("/employer/organizations"),
    createOrganization: (name: string) => request<Record<string, unknown>>("/employer/organizations", { method: "POST", body: JSON.stringify({ name }) }),
    dashboard: (organizationId: string) => request<Record<string, unknown>>(`/employer/organizations/${organizationId}/dashboard`),
    jobs: (organizationId: string) => request<Array<Record<string, unknown>>>(`/employer/organizations/${organizationId}/jobs`),
    createJob: (organizationId: string, payload: Record<string, unknown>) => request<Record<string, unknown>>(`/employer/organizations/${organizationId}/jobs`, { method: "POST", body: JSON.stringify(payload) }),
    publishJob: (jobId: string) => request<Record<string, unknown>>(`/employer/jobs/${jobId}/publish`, { method: "POST" }),
    closeJob: (jobId: string) => request<Record<string, unknown>>(`/employer/jobs/${jobId}/close`, { method: "POST" }),
    applicants: (jobId: string) => request<Array<Record<string, unknown>>>(`/employer/jobs/${jobId}/applicants`),
    updateApplicant: (applicantId: string, payload: Record<string, unknown>) => request<Record<string, unknown>>(`/employer/applicants/${applicantId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  },
};
