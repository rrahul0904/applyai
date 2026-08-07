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

export const platformApi = {
  semanticMatches: (limit = 25) => request<{ engine: string; items: SemanticMatch[] }>(`/semantic-matches?limit=${limit}`),
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
    export: (id: string, format: "txt" | "html" = "txt") => request<{ filename: string; content: string; content_type: string; version: number }>(`/resume-studio/${id}/export?format=${format}`),
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
