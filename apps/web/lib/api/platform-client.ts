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

export type InterviewQuestion = {
  id: string;
  mode: string;
  prompt: string;
  model_answer: string;
  rubric: Record<string, number>;
  followups: string[];
  display_order: number;
};

export type InterviewPhase = {
  id: string;
  phase_number: number;
  phase_type: string;
  title: string;
  status: string;
  prep: { focus?: string[]; target_questions?: string[]; carry_forward?: string[] };
  quiz: Array<{ id: string; question: string; options: string[]; correct_index: number; explanation: string }>;
  flashcards: Array<{ front: string; back: string }>;
  notes: string | null;
  reflection: Record<string, unknown>;
  cheat_sheet: { remember?: string[]; stories?: string[]; questions_to_ask?: string[] };
  readiness: { score?: number; attempt_count?: number };
  questions: InterviewQuestion[];
};

export type PodcastEpisode = {
  id: string;
  episode_number: number;
  title: string;
  summary: string;
  script: Array<{ speaker: string; text: string }>;
  duration_estimate_minutes: number;
  audio_url: string | null;
  status: string;
};

export type InterviewPreparation = {
  id: string;
  job_id: string;
  job: { title: string; description: string };
  status: string;
  country: string | null;
  interview_date: string | null;
  current_phase_number: number;
  interviewer: { name: string | null; title: string | null; url: string | null; brief: Record<string, unknown> };
  company_research: Record<string, unknown>;
  role_analysis: Record<string, unknown>;
  resume_analysis: Record<string, unknown>;
  market_benchmark: Record<string, unknown>;
  readiness: { overall?: number; practice?: number; round_learning?: number; notes?: number; attempt_count?: number };
  private_feed_token: string;
  phases: InterviewPhase[];
  episodes: PodcastEpisode[];
  research_sources: Array<{ id: string; source_kind: string; title: string; url: string | null; snippet: string | null; source_metadata: Record<string, unknown>; created_at: string }>;
};

export type InterviewAttemptResult = {
  id: string;
  score: number;
  feedback: {
    word_count?: number;
    strengths?: string[];
    improvements?: string[];
    model_answer?: string;
    next_followup?: string;
    dimensions?: Record<string, number>;
    scoring_note?: string;
  };
  phase_readiness: Record<string, unknown>;
  overall_readiness: Record<string, unknown>;
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
  interviewIntelligence: {
    get: (jobId: string) => request<InterviewPreparation>(`/interview-intelligence/${jobId}`),
    bootstrap: (jobId: string, payload: Record<string, unknown>) => request<InterviewPreparation>(`/interview-intelligence/${jobId}/bootstrap`, { method: "POST", body: JSON.stringify(payload) }),
    regenerate: (jobId: string) => request<InterviewPreparation>(`/interview-intelligence/${jobId}/regenerate`, { method: "POST" }),
    saveNotes: (phaseId: string, notes: string) => request<{ id: string; notes: string; readiness: Record<string, unknown> }>(`/interview-intelligence/phases/${phaseId}/notes`, { method: "PUT", body: JSON.stringify({ notes }) }),
    saveReflection: (phaseId: string, payload: Record<string, unknown>) => request<{ reflection: Record<string, unknown>; next_phase_number: number; readiness: Record<string, unknown> }>(`/interview-intelligence/phases/${phaseId}/reflection`, { method: "POST", body: JSON.stringify(payload) }),
    submitAttempt: (questionId: string, payload: { answer_text: string; transcript_source?: string; duration_seconds?: number | null }) => request<InterviewAttemptResult>(`/interview-intelligence/questions/${questionId}/attempts`, { method: "POST", body: JSON.stringify(payload) }),
    attempts: (questionId: string) => request<Array<Record<string, unknown>>>(`/interview-intelligence/questions/${questionId}/attempts`),
    addResearchSource: (jobId: string, payload: Record<string, unknown>) => request<Record<string, unknown>>(`/interview-intelligence/${jobId}/research-sources`, { method: "POST", body: JSON.stringify(payload) }),
    stories: () => request<Array<Record<string, unknown>>>("/interview-intelligence/stories/all"),
    createStory: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/interview-intelligence/stories", { method: "POST", body: JSON.stringify(payload) }),
    feedPath: (token: string) => `/api/backend/interview-intelligence/feed/${token}.xml`,
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
    applicants: (jobId: string) => request<Array<Record<string, unknown>>(`/employer/jobs/${jobId}/applicants`),
    updateApplicant: (applicantId: string, payload: Record<string, unknown>) => request<Record<string, unknown>>(`/employer/applicants/${applicantId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  },
};
