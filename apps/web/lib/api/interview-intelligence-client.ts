export type InterviewQuestion = {
  id: string;
  slug: string;
  title: string;
  track: string;
  difficulty: string;
  summary: string;
  prompt: string;
  companies: string[];
  stages: string[];
  skills: string[];
  patterns: string[];
  hints: string[];
  follow_ups: string[];
  solution_outline: string[];
  frequency_score: number;
  confidence: number;
  report_count: number;
  last_reported_at: string | null;
};

export type InterviewProgress = {
  total_attempts: number;
  by_track: Record<string, { attempts: number; average_score: number }>;
  by_question: Record<string, { attempts: number; best_score: number | null; latest_score: number | null }>;
};

export type InterviewLifecyclePhase = {
  phase_number: number;
  phase_type: string;
  title: string;
  prep: { focus?: string[]; strengths?: string[]; gaps?: string[] };
  questions: { order: number; prompt: string; evidence_guidance: string }[];
  quiz: { question: string; answer: string }[];
  flashcards: { front: string; back: string }[];
  cheat_sheet: Record<string, unknown>;
  notes: string;
  reflection: Record<string, unknown>;
  carry_forward: string[];
};

export type InterviewWorkspace = {
  id: string;
  job_id: string;
  current_phase_number: number;
  interview_date: string | null;
  interviewer: { name: string | null; title: string | null; url: string | null };
  lifecycle: {
    job_title: string;
    company: string;
    gaps: string[];
    strengths: string[];
    phases: InterviewLifecyclePhase[];
    carry_forward: string[];
  };
  readiness: { score: number; band: string; phase: number; reflections_completed: number; notes_completed: number; practice_average?: number | null };
  podcasts: { episode_number: number; title: string; summary: string; script: { speaker: string; text: string }[]; playback: string }[];
  research_sources: unknown[];
  status: string;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend/api/v1/interview-intelligence${path}`, {
    ...init,
    headers: init.body instanceof FormData ? init.headers : { "content-type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(body?.error?.message ?? `Interview intelligence request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const interviewIntelligenceApi = {
  capabilities: (signal?: AbortSignal) => request<Record<string, unknown>>("/capabilities", { signal }),
  workspace: (jobId: string, signal?: AbortSignal) => request<InterviewWorkspace>(`/workspaces/${jobId}`, { signal }),
  bootstrap: (jobId: string, payload: Record<string, unknown> = {}) => request<InterviewWorkspace>(`/workspaces/${jobId}`, { method: "POST", body: JSON.stringify(payload) }),
  notes: (jobId: string, phase: number, notes: string) => request<InterviewWorkspace>(`/workspaces/${jobId}/phases/${phase}/notes`, { method: "PUT", body: JSON.stringify({ notes }) }),
  reflect: (jobId: string, phase: number, payload: Record<string, unknown>) => request<InterviewWorkspace>(`/workspaces/${jobId}/phases/${phase}/reflection`, { method: "POST", body: JSON.stringify(payload) }),
  stories: (signal?: AbortSignal) => request<Array<Record<string, unknown>>>("/stories", { signal }),
  createStory: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/stories", { method: "POST", body: JSON.stringify(payload) }),
  questions: (params = "", signal?: AbortSignal) => request<{ items: InterviewQuestion[]; total: number }>(`/questions${params ? `?${params}` : ""}`, { signal }),
  question: (slug: string, signal?: AbortSignal) => request<InterviewQuestion>(`/questions/${encodeURIComponent(slug)}`, { signal }),
  companies: (signal?: AbortSignal) => request<Array<{ name: string; slug: string; question_count: number; report_count: number; tracks: Record<string, number>; stages: Record<string, number> }>>("/companies", { signal }),
  progress: (signal?: AbortSignal) => request<InterviewProgress>("/progress", { signal }),
  attempt: (payload: Record<string, unknown>) => request<{ id: string; status: string; score: number; feedback: Record<string, unknown> }>("/attempts", { method: "POST", body: JSON.stringify(payload) }),
  coach: (questionId: string, answer: string, hintLevel: number) => request<{ level: number; hint: string; next_level: number }>("/coach", { method: "POST", body: JSON.stringify({ question_id: questionId, answer, hint_level: hintLevel }) }),
  submitReport: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/reports", { method: "POST", body: JSON.stringify(payload) }),
  community: (signal?: AbortSignal) => request<Array<Record<string, unknown>>>("/community", { signal }),
  createCommunity: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/community", { method: "POST", body: JSON.stringify(payload) }),
};
