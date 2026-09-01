export type RecruiterLensMode =
  | "DEFAULT_RECRUITER"
  | "STRICT_MUST_HAVE"
  | "HIRING_MANAGER"
  | "TECHNICAL"
  | "CUSTOM";

export type RecruiterLensCriterion = {
  id: string;
  label: string;
  category: string;
  required: boolean;
  weight: number | null;
  status: "SUPPORTED" | "PARTIAL" | "NOT_EVIDENCED";
  evidence: {
    kind: string;
    label: string;
    snippet: string;
  } | null;
};

export type RecruiterLensSnapshot = {
  engine_version: string;
  mode: RecruiterLensMode;
  criteria_set_id: string | null;
  score: number;
  tier: "A" | "B" | "C" | "D";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  criteria_source: "STRUCTURED_JOB_POSTING" | "CANDIDATE_CUSTOM";
  counts: {
    supported: number;
    partial: number;
    not_evidenced: number;
  };
  criteria: RecruiterLensCriterion[];
  concerns: Array<{
    criterion_id: string;
    severity: "HIGH" | "MEDIUM";
    message: string;
  }>;
  interview_questions: Array<{
    criterion_id: string;
    focus: string;
    question: string;
  }>;
  report: {
    print_friendly: boolean;
    generated_for_candidate_self_assessment: boolean;
    share_requires_candidate_control: boolean;
  };
  disclaimer: string;
  policy: {
    candidate_self_assessment: true;
    employer_prediction: false;
    identity_fields_used: false;
    evidence_policy: "VERIFIED_EVIDENCE_ONLY";
    protected_characteristic_criteria_allowed: false;
  };
};

export class RecruiterLensError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "RecruiterLensError";
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    headers: { "content-type": "application/json" },
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: { code?: string; message?: string } }
      | null;
    throw new RecruiterLensError(
      response.status,
      payload?.error?.code || "RECRUITER_LENS_ERROR",
      payload?.error?.message || "We could not build Recruiter Lens for this role.",
    );
  }
  return response.json() as Promise<T>;
}

export const recruiterLensApi = {
  get: (
    jobId: string,
    options?: { mode?: RecruiterLensMode; criteriaSetId?: string | null },
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams();
    if (options?.mode) params.set("mode", options.mode);
    if (options?.criteriaSetId) params.set("criteria_set_id", options.criteriaSetId);
    const suffix = params.size ? `?${params.toString()}` : "";
    return request<RecruiterLensSnapshot>(`/recruiter-lens/jobs/${jobId}${suffix}`, signal);
  },
};
