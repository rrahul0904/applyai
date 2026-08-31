export type CareerSystemStage = {
  id: string;
  label: string;
  complete: boolean;
  weight: number;
};

export type CareerSystemSnapshot = {
  job_id: string;
  job_title: string;
  company_name: string;
  application_id: string | null;
  application_status: string | null;
  progress_score: number;
  progress_explanation: string;
  next_action: CareerSystemStage | null;
  stages: CareerSystemStage[];
  resume: {
    version_id: string | null;
    filename: string | null;
    upload_status: string | null;
    processing_status: string | null;
    ready: boolean;
  };
  match: {
    match_score: number;
    fit_band: string;
    decision: string;
    confidence: string;
    matched_skills: string[];
    missing_skills: string[];
    missing_requirements: string[];
    strengths: string[];
    risks: string[];
    summary: string;
  };
  application_package: {
    readiness_score: number;
    ready_to_finalize: boolean;
    cover_letter_verified: boolean;
    question_count: number;
    verified_question_count: number;
    checklist: Array<{ id: string; label: string; complete: boolean; weight: number }>;
  };
  communications: {
    recruiter_message: string;
    recruiter_message_verified: boolean;
    follow_up_message: string;
    follow_up_message_verified: boolean;
    policy: string;
  };
  portfolio_preview: {
    headline: string;
    about: string;
    target_context: string;
    highlights: Array<{
      title: string;
      company: string;
      description: string | null;
      provenance: string;
    }>;
    skills: string[];
    safety: { policy: string; message: string };
  };
  interview: {
    ready: boolean;
    artifact_id: string | null;
    status: string;
    candidate_verified: boolean;
    content: Record<string, unknown> | null;
    starter_questions: Array<{ focus: string; question: string }>;
  };
  actions: {
    resume: string;
    career_memory: string;
    application: string | null;
    interview_task: "interview-prep";
  };
  safety: {
    evidence_policy: string;
    external_action_policy: string;
  };
};

export type CareerSystemCommunicationWrite = {
  recruiter_message: string;
  recruiter_message_verified: boolean;
  follow_up_message: string;
  follow_up_message_verified: boolean;
};

export class CareerSystemError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "CareerSystemError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init.headers || {}) },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: { code?: string; message?: string } }
      | null;
    throw new CareerSystemError(
      response.status,
      payload?.error?.code || "CAREER_SYSTEM_ERROR",
      payload?.error?.message || "We could not load your Career System.",
    );
  }
  return response.json() as Promise<T>;
}

export const careerSystemApi = {
  get: (jobId: string, signal?: AbortSignal) =>
    request<CareerSystemSnapshot>(`/career-system/jobs/${jobId}`, { signal }),
  saveCommunications: (jobId: string, payload: CareerSystemCommunicationWrite) =>
    request<CareerSystemSnapshot>(`/career-system/jobs/${jobId}/communications`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
