export type SkillGap = {
  id: string;
  skill: string;
  normalized_skill: string;
  requirement_level: string;
  candidate_level: string;
  severity: string;
  priority: number;
  status: string;
  reason: string;
  recommended_action: string;
  confidence: number;
};

export type Readiness = {
  job_id: string;
  overall_score: number;
  band: string;
  breakdown: Record<string, { score: number; weight: number }>;
  top_skill_gaps: SkillGap[];
  next_actions: string[];
};

export type LearningPath = {
  id: string;
  job_id: string;
  title: string;
  status: string;
  estimated_minutes: number;
  completion_percent: number;
  strategy: Record<string, unknown>;
  skills: Array<{ skill: string; position: number; target_level: string; status: string }>;
  courses: Array<{ id: string; skill: string; title: string; summary: string; estimated_minutes: number; status: string }>;
};

export type Course = {
  id: string;
  job_id: string;
  skill: string;
  title: string;
  summary: string;
  level: string;
  estimated_minutes: number;
  modules: Array<{
    id: string;
    position: number;
    title: string;
    objective: string;
    lessons: Array<{
      id: string;
      title: string;
      content_markdown: string;
      summary: string;
      estimated_minutes: number;
      key_points: string[];
      resources: Array<Record<string, unknown>>;
      completed: boolean;
      mastery_score: number | null;
      exercises: Array<{ id: string; type: string; prompt: string; difficulty: string }>;
    }>;
  }>;
};

export type InterviewPack = {
  id: string;
  job_id: string;
  title: string;
  strategy_summary: string;
  status: string;
  sections: Array<{ type: string; title: string; content: Record<string, unknown> }>;
};

export type MockInterview = {
  id: string;
  job_id: string;
  mode: string;
  channel: string;
  difficulty: string;
  status: string;
  provider: string;
  overall_score: number | null;
  category_scores: Record<string, number>;
  feedback: Record<string, unknown>;
  current_question: { turn_id: string; question: string; position: number } | null;
  turns: Array<{
    id: string;
    position: number;
    question: string;
    answer: string | null;
    score: number | null;
    evaluation: Record<string, unknown>;
    follow_up: boolean;
  }>;
};

type ErrorEnvelope = { error?: { code?: string; message?: string } };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: init.body instanceof FormData ? init.headers : { "content-type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorEnvelope | null;
    throw new Error(payload?.error?.message ?? "ApplyAI Prepare could not complete that request.");
  }
  return response.json() as Promise<T>;
}

export const prepareApi = {
  readiness: (jobId: string, signal?: AbortSignal) => request<Readiness>(`/career-v2/jobs/${jobId}/readiness`, { signal }),
  skillGaps: (jobId: string, signal?: AbortSignal) => request<{ job_id: string; items: SkillGap[] }>(`/career-v2/jobs/${jobId}/skill-gaps`, { signal }),
  analyzeSkills: (jobId: string) => request<{ job_id: string; items: SkillGap[]; open_gap_count: number }>(`/career-v2/jobs/${jobId}/skill-analysis`, { method: "POST" }),
  createLearningPath: (jobId: string) => request<LearningPath>(`/career-v2/jobs/${jobId}/learning-path`, { method: "POST" }),
  learningPath: (pathId: string, signal?: AbortSignal) => request<LearningPath>(`/career-v2/learning-paths/${pathId}`, { signal }),
  course: (courseId: string, signal?: AbortSignal) => request<Course>(`/career-v2/courses/${courseId}`, { signal }),
  setLessonProgress: (lessonId: string, completed: boolean, masteryScore?: number) => request<{ lesson_id: string; completed: boolean; mastery_score: number | null }>(`/career-v2/lessons/${lessonId}/progress`, { method: "PUT", body: JSON.stringify({ completed, mastery_score: masteryScore ?? null }) }),
  lessonChat: (lessonId: string, message: string) => request<{ lesson_id: string; answer: string; grounded_in: string[]; provider: string }>(`/career-v2/lessons/${lessonId}/chat`, { method: "POST", body: JSON.stringify({ message }) }),
  exerciseAttempt: (exerciseId: string, response: string) => request<{ attempt_id: string; score: number; feedback: Record<string, unknown> }>(`/career-v2/exercises/${exerciseId}/attempts`, { method: "POST", body: JSON.stringify({ response }) }),
  createInterviewPack: (jobId: string) => request<InterviewPack>(`/career-v2/jobs/${jobId}/interview-pack`, { method: "POST" }),
  interviewPack: (jobId: string, signal?: AbortSignal) => request<InterviewPack>(`/career-v2/jobs/${jobId}/interview-pack`, { signal }),
  startMock: (jobId: string, mode: string, channel: "WRITTEN" | "VOICE" | "VIDEO" = "WRITTEN") => request<MockInterview>(`/career-v2/jobs/${jobId}/mock-interviews`, { method: "POST", body: JSON.stringify({ mode, channel, difficulty: "adaptive" }) }),
  answerMock: (sessionId: string, answer: string) => request<MockInterview>(`/career-v2/interviews/${sessionId}/answers`, { method: "POST", body: JSON.stringify({ answer }) }),
  completeMock: (sessionId: string) => request<MockInterview>(`/career-v2/interviews/${sessionId}/complete`, { method: "POST" }),
  report: (sessionId: string, signal?: AbortSignal) => request<MockInterview>(`/career-v2/interviews/${sessionId}/report`, { signal }),
  saveRecording: (sessionId: string, payload: { media_type: "AUDIO" | "VIDEO"; storage_key: string; transcript_text?: string | null; duration_seconds?: number | null; provider?: string }) => request<{ recording_id: string; media_type: string; duration_seconds: number | null; transcript_available: boolean }>(`/career-v2/interviews/${sessionId}/recordings`, { method: "POST", body: JSON.stringify(payload) }),
  progress: (jobId: string, signal?: AbortSignal) => request<{ job_id: string; snapshots: Array<Record<string, unknown>> }>(`/career-v2/jobs/${jobId}/progress`, { signal }),
};
