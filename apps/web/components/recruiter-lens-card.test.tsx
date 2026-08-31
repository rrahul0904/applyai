import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RecruiterLensCard } from "@/components/recruiter-lens-card";
import {
  recruiterLensApi,
  type RecruiterLensSnapshot,
} from "@/lib/api/recruiter-lens";

vi.mock("@/lib/api/recruiter-lens", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/recruiter-lens")>();
  return {
    ...original,
    recruiterLensApi: { get: vi.fn() },
  };
});

const snapshot: RecruiterLensSnapshot = {
  engine_version: "applyai-recruiter-lens-v1",
  score: 74,
  tier: "B",
  confidence: "HIGH",
  criteria_source: "STRUCTURED_JOB_POSTING",
  counts: { supported: 3, partial: 1, not_evidenced: 1 },
  criteria: [
    {
      id: "required-skill-0",
      label: "Python",
      category: "REQUIRED_SKILL",
      required: true,
      status: "SUPPORTED",
      evidence: {
        kind: "VERIFIED_SKILL",
        label: "Verified skill",
        snippet: "Python",
      },
    },
    {
      id: "required-skill-1",
      label: "Kubernetes",
      category: "REQUIRED_SKILL",
      required: true,
      status: "NOT_EVIDENCED",
      evidence: null,
    },
  ],
  concerns: [
    {
      criterion_id: "required-skill-1",
      severity: "HIGH",
      message: "ApplyAI could not find verified evidence for Kubernetes in your saved career profile.",
    },
  ],
  interview_questions: [
    {
      criterion_id: "required-skill-1",
      focus: "Kubernetes",
      question:
        "The role appears to value Kubernetes, but it is not explicit in your saved evidence. Do you have a truthful adjacent example you can explain without overstating your experience?",
    },
  ],
  disclaimer:
    "Recruiter Lens is a candidate-side screening simulation based on the job posting and your saved verified evidence. It is not an employer score, hiring probability, or automated employment decision.",
  policy: {
    candidate_self_assessment: true,
    employer_prediction: false,
    identity_fields_used: false,
    evidence_policy: "VERIFIED_EVIDENCE_ONLY",
  },
};

function renderLens() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RecruiterLensCard jobId="job-1" />
    </QueryClientProvider>,
  );
}

describe("RecruiterLensCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(recruiterLensApi.get).mockResolvedValue(snapshot);
  });

  it("renders the readiness tier, score, evidence, gaps, and disclaimer", async () => {
    renderLens();

    expect(await screen.findByRole("heading", { name: "Recruiter Lens" })).toBeDefined();
    expect(screen.getByLabelText("Recruiter Lens tier B")).toBeDefined();
    expect(screen.getByText("74%")).toBeDefined();
    expect(screen.getByText("Python")).toBeDefined();
    expect(screen.getAllByText("Kubernetes").length).toBeGreaterThan(0);
    expect(screen.getByText(/could not find verified evidence for Kubernetes/i)).toBeDefined();
    expect(screen.getByText(/truthful adjacent example/i)).toBeDefined();
    expect(screen.getByText(/not an employer score/i)).toBeDefined();
  });
});
