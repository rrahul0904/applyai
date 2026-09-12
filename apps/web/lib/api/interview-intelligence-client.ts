export type InterviewQuestion = {
  id: string;
  slug: string;
  title: string;
  track: string;
  difficulty: string;
  summary: string;
  prompt: string;
  companies: string[];
  skills: string[];
  patterns: string[];
  hints: string[];
  follow_ups: string[];
  solution_outline: string[];
  test_cases: Array<Record<string, unknown>>;
  starter_code: Record<string, string>;
  frequency_score: number;
  confidence: number;
  report_count: number;
  last_reported_at: string | null;
};

export type QuestionPage = { items: InterviewQuestion[]; total: number; offset: number; limit: number; next_offset: number | null };
export type CompanyCollection = { name: string; slug: string; question_count: number; report_count: number; tracks: Record<string, number>; questions?: InterviewQuestion[] };
export type InterviewProgress = { total_attempts: number; completed: number; by_track: Record<string, { attempts: number; completed: number; average_score: number }> };
export type PreparationPlan = { id: string; job_id: string; job_title: string | null; company: string | null; readiness_score: number; strengths: string[]; gaps: string[]; actions: Array<{ order: number; track: string; question_count: number; reason: string }>; updated_at: string };
export type CommunityPost = { id: string; company: string | null; category: string; title: string; body: string; reaction_count: number; reply_count: number; view_count: number; created_at: string; replies?: Array<{ id: string; body: string; created_at: string }> };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend/interview-intelligence${path}`, {
    ...init,
    headers: init.body ? { "content-type": "application/json", ...init.headers } : init.headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
    throw new Error(body?.error?.message ?? `Interview intelligence request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const interviewIntelligenceApi = {
  capabilities: () => request<{ tracks: string[]; features: Record<string, boolean>; execution_boundary: string; clean_room: boolean }>("/capabilities"),
  questions: (params: URLSearchParams = new URLSearchParams()) => request<QuestionPage>(`/questions${params.size ? `?${params}` : ""}`),
  question: (slug: string) => request<InterviewQuestion>(`/questions/${encodeURIComponent(slug)}`),
  companies: () => request<CompanyCollection[]>("/companies"),
  company: (slug: string) => request<CompanyCollection>(`/companies/${encodeURIComponent(slug)}`),
  progress: () => request<InterviewProgress>("/progress"),
  createAttempt: (payload: Record<string, unknown>) => request<{ id: string; status: string }>("/attempts", { method: "POST", body: JSON.stringify(payload) }),
  updateAttempt: (id: string, payload: Record<string, unknown>) => request<Record<string, unknown>>(`/attempts/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  coach: (payload: { question_id: string; answer?: string; hint_level: number }) => request<{ level: number; hint: string; next_level: number; provider: string }>("/coach", { method: "POST", body: JSON.stringify(payload) }),
  getPlan: (jobId: string) => request<PreparationPlan>(`/plans/${jobId}`),
  createPlan: (jobId: string) => request<PreparationPlan>(`/plans/${jobId}`, { method: "POST", body: "{}" }),
  startMock: (jobId: string, mode: string) => request<{ id: string; mode: string; provider: string; questions: Array<Record<string, unknown>>; execution_boundary: string }>(`/mock/${jobId}/start?mode=${encodeURIComponent(mode)}`, { method: "POST" }),
  community: (params: URLSearchParams = new URLSearchParams()) => request<CommunityPost[]>(`/community${params.size ? `?${params}` : ""}`),
  createCommunityPost: (payload: Record<string, unknown>) => request<CommunityPost>("/community", { method: "POST", body: JSON.stringify(payload) }),
  react: (id: string) => request<{ reacted: boolean; reaction_count: number }>(`/community/${id}/react`, { method: "POST" }),
  submitReport: (payload: Record<string, unknown>) => request<{ id: string; moderation_status: string; duplicate: boolean }>("/reports", { method: "POST", body: JSON.stringify(payload) }),
};
