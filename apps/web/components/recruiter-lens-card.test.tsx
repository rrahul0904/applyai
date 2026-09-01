import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RecruiterLensCard } from "@/components/recruiter-lens-card";
import { growthApi } from "@/lib/api/growth";
import { recruiterLensApi, type RecruiterLensSnapshot } from "@/lib/api/recruiter-lens";

const { successMock, errorMock } = vi.hoisted(() => ({
  successMock: vi.fn(),
  errorMock: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: successMock, error: errorMock } }));
vi.mock("@/lib/api/growth", () => ({
  growthApi: {
    criteriaSets: {
      list: vi.fn(),
      create: vi.fn(),
    },
  },
}));
vi.mock("@/lib/api/recruiter-lens", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/recruiter-lens")>();
  return {
    ...original,
    recruiterLensApi: {
      get: vi.fn(),
      createReportShare: vi.fn(),
      revokeReportShare: vi.fn(),
    },
  };
});

const snapshot: RecruiterLensSnapshot = {
  engine_version: "applyai-recruiter-lens-v2",
  mode: "DEFAULT_RECRUITER",
  criteria_set_id: null,
  score: 82,
  tier: "B",
  confidence: "HIGH",
  criteria_source: "STRUCTURED_JOB_POSTING",
  counts: { supported: 1, partial: 1, not_evidenced: 0 },
  criteria: [
    {
      id: "skill-python",
      label: "Python",
      category: "SKILL",
      required: true,
      weight: 2,
      status: "SUPPORTED",
      evidence: { kind: "SKILL", label: "Python", snippet: "Verified Python experience" },
    },
    {
      id: "leadership",
      label: "Leadership",
      category: "REQUIREMENT",
      required: true,
      weight: 2,
      status: "PARTIAL",
      evidence: { kind: "EXPERIENCE", label: "Leadership", snippet: "Led a verified team" },
    },
  ],
  concerns: [],
  interview_questions: [],
  report: {
    print_friendly: true,
    generated_for_candidate_self_assessment: true,
    share_requires_candidate_control: true,
  },
  disclaimer: "This is not an employer score or hiring probability.",
  policy: {
    candidate_self_assessment: true,
    employer_prediction: false,
    identity_fields_used: false,
    evidence_policy: "VERIFIED_EVIDENCE_ONLY",
    protected_characteristic_criteria_allowed: false,
  },
};

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RecruiterLensCard jobId="job-1" />
    </QueryClientProvider>,
  );
}

describe("RecruiterLensCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(growthApi.criteriaSets.list).mockResolvedValue([]);
    vi.mocked(recruiterLensApi.get).mockResolvedValue(snapshot);
    vi.mocked(recruiterLensApi.createReportShare).mockResolvedValue({
      id: "share-1",
      job_id: "job-1",
      mode: "DEFAULT_RECRUITER",
      criteria_set_id: null,
      public_path: "/recruiter-report/report-token-12345678901234567890",
      revoked: false,
      created_at: "2026-09-01T00:00:00Z",
      privacy: { candidate_controlled: true, named_viewer_tracking: false, employer_decision: false },
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("exposes candidate-only screening perspectives and disclaimer", async () => {
    renderCard();
    expect(await screen.findByRole("heading", { name: "Recruiter Lens" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Strict must-have" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Hiring manager" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Technical" })).toBeDefined();
    expect(screen.getByText(/not an employer score or hiring probability/i)).toBeDefined();
  });

  it("creates and copies a candidate-controlled private report link", async () => {
    renderCard();
    fireEvent.click(await screen.findByRole("button", { name: /share private report/i }));

    await waitFor(() => expect(recruiterLensApi.createReportShare).toHaveBeenCalledWith(
      "job-1",
      { mode: "DEFAULT_RECRUITER", criteriaSetId: null },
    ));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining("/recruiter-report/report-token-12345678901234567890"),
    );
    expect(successMock).toHaveBeenCalledWith("Private Recruiter Lens report link copied");
  });
});
