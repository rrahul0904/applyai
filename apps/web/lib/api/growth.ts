type ErrorPayload = { error?: { message?: string } };

async function growthRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: init.body ? { "content-type": "application/json", ...init.headers } : init.headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
    throw new Error(payload?.error?.message ?? "ApplyAI could not complete that request.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type PortfolioProject = {
  id: string;
  title: string;
  summary: string;
  role: string | null;
  technologies: string[];
  verified_outcome: string | null;
  project_url: string | null;
  repository_url: string | null;
  media_url: string | null;
  project_date: string | null;
  visible: boolean;
};

export type Portfolio = {
  configured: boolean;
  suggested_slug?: string;
  slug?: string;
  public_path?: string;
  published: boolean;
  theme: string;
  indexing_allowed?: boolean;
  headline?: string | null;
  about?: string | null;
  visibility: Record<string, boolean>;
  contact_enabled?: boolean;
  projects: PortfolioProject[];
};

export type CareerNavigation = {
  current_role: string | null;
  target_role: string;
  target_roles: string[];
  adjacent_roles: Array<{ role: string; posting_count: number; reason: string }>;
  evidence_strengths: Array<{ skill: string; posting_count: number; evidenced: boolean }>;
  skill_gaps: Array<{ skill: string; posting_count: number; evidenced: boolean }>;
  preparation: string[];
  market: {
    sample_size: number;
    freshest_observation: string | null;
    coverage_caveat: string;
    work_modes: Record<string, number>;
    locations: Array<{ location: string; count: number }>;
    seniority: Record<string, number>;
    top_skills: Array<{ skill: string; posting_count: number; evidenced: boolean }>;
    common_requirement_terms: Array<{ term: string; count: number }>;
    salary: { sample_size: number; median_explicit_usd_yearly_midpoint: number | null; inferred: false };
  };
};

export type CriteriaSet = {
  id: string;
  name: string;
  mode: string;
  criteria: Array<{ label: string; required: boolean; weight: number }>;
  archived: boolean;
  updated_at: string;
};

export type InterviewAttempt = {
  id: string;
  job_id: string | null;
  category: string;
  question: string;
  answer_text: string | null;
  notes: string | null;
  self_review: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type InterviewLab = {
  job_id: string;
  job_title: string;
  questions: Array<{ category: string; question: string }>;
  attempts: InterviewAttempt[];
  execution_policy: { remote_arbitrary_code_execution: boolean; reason: string };
};

export const growthApi = {
  portfolio: {
    get: (signal?: AbortSignal) => growthRequest<Portfolio>("/growth/portfolio", { signal }),
    save: (payload: Record<string, unknown>) => growthRequest<Portfolio>("/growth/portfolio", { method: "PUT", body: JSON.stringify(payload) }),
    createProject: (payload: Record<string, unknown>) => growthRequest<PortfolioProject>("/growth/portfolio/projects", { method: "POST", body: JSON.stringify(payload) }),
    updateProject: (id: string, payload: Record<string, unknown>) => growthRequest<PortfolioProject>(`/growth/portfolio/projects/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
    deleteProject: (id: string) => growthRequest<void>(`/growth/portfolio/projects/${id}`, { method: "DELETE" }),
  },
  careerNavigation: (targetRole?: string, signal?: AbortSignal) => {
    const params = new URLSearchParams();
    if (targetRole) params.set("target_role", targetRole);
    const suffix = params.size ? `?${params.toString()}` : "";
    return growthRequest<CareerNavigation>(`/growth/career-navigation${suffix}`, { signal });
  },
  criteriaSets: {
    list: (signal?: AbortSignal) => growthRequest<CriteriaSet[]>("/growth/recruiter-lens/criteria-sets", { signal }),
    create: (payload: Record<string, unknown>) => growthRequest<CriteriaSet>("/growth/recruiter-lens/criteria-sets", { method: "POST", body: JSON.stringify(payload) }),
    update: (id: string, payload: Record<string, unknown>) => growthRequest<CriteriaSet>(`/growth/recruiter-lens/criteria-sets/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
    archive: (id: string) => growthRequest<CriteriaSet>(`/growth/recruiter-lens/criteria-sets/${id}/archive`, { method: "POST" }),
  },
  interview: {
    get: (jobId: string, signal?: AbortSignal) => growthRequest<InterviewLab>(`/growth/interview-lab/jobs/${jobId}`, { signal }),
    createAttempt: (payload: Record<string, unknown>) => growthRequest<InterviewAttempt>("/growth/interview-lab/attempts", { method: "POST", body: JSON.stringify(payload) }),
  },
  resumeShare: {
    sessions: (shareId: string, signal?: AbortSignal) => growthRequest<Record<string, unknown>>(`/resume-shares/${shareId}/sessions`, { signal }),
    trends: (shareId: string, days: 7 | 30 | 90, signal?: AbortSignal) => growthRequest<Record<string, unknown>>(`/resume-shares/${shareId}/trends?days=${days}`, { signal }),
  },
};
