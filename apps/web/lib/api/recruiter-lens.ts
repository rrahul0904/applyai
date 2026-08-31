export type RecruiterLensCriterion = {
  id: string;
  label: string;
  category: string;
  required: boolean;
  status: "SUPPORTED" | "PARTIAL" | "NOT_EVIDENCED";
  evidence: {
    kind: string;
    label: string;
    snippet: string;
  } | null;
};

export type RecruiterLensSnapshot = {
  engine_version: string;
  score: number;
  tier: "A" | "B" | "C" | "D";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  criteria_source: "STRUCTURED_JOB_POSTING";
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
  disclaimer: string;
  policy: {
    candidate_self_assessment: true;
    employer_prediction: false;
    identity_fields_used: false;
    evidence_policy: "VERIFIED_EVIDENCE_ONLY";
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
  get: (jobId: string, signal?: AbortSignal) =>
    request<RecruiterLensSnapshot>(`/recruiter-lens/jobs/${jobId}`, signal),
};
