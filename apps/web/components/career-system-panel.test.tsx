import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CareerSystemPanel } from "@/components/career-system-panel";
import { api } from "@/lib/api/client";
import { careerSystemApi, type CareerSystemSnapshot } from "@/lib/api/career-system";

const { successMock, errorMock } = vi.hoisted(() => ({
  successMock: vi.fn(),
  errorMock: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: successMock,
    error: errorMock,
  },
}));

vi.mock("@/lib/api/client", () => ({
  api: {
    applications: { create: vi.fn() },
    careerV2: { start: vi.fn(), run: vi.fn() },
  },
}));

vi.mock("@/lib/api/career-system", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/career-system")>();
  return {
    ...original,
    careerSystemApi: {
      get: vi.fn(),
      saveCommunications: vi.fn(),
    },
  };
});

const snapshot: CareerSystemSnapshot = {
  job_id: "job-1",
  job_title: "Senior Data Engineer",
  company_name: "ApplyAI Labs",
  application_id: null,
  application_status: null,
  progress_score: 30,
  progress_explanation:
    "Career System progress measures completion of your preparation workflow. It is not a hiring probability or employer prediction.",
  next_action: {
    id: "resume",
    label: "Processed master resume",
    complete: false,
    weight: 15,
  },
  stages: [
    { id: "profile", label: "Verified career profile", complete: true, weight: 15 },
    { id: "resume", label: "Processed master resume", complete: false, weight: 15 },
    { id: "fit", label: "Role fit analyzed", complete: true, weight: 15 },
    { id: "package", label: "Application package reviewed", complete: false, weight: 25 },
    { id: "outreach", label: "Outreach and follow-up reviewed", complete: false, weight: 10 },
    { id: "interview", label: "Interview preparation created", complete: false, weight: 10 },
    { id: "application", label: "Application workspace started", complete: false, weight: 10 },
  ],
  resume: {
    version_id: null,
    filename: null,
    upload_status: null,
    processing_status: null,
    ready: false,
  },
  match: {
    match_score: 78,
    fit_band: "GOOD",
    decision: "CONSIDER",
    confidence: "HIGH",
    matched_skills: ["Python", "SQL", "AWS"],
    missing_skills: ["Kafka"],
    missing_requirements: [],
    strengths: ["Verified skills align."],
    risks: ["Kafka is not yet explicit."],
    summary: "Strong technical overlap with one explicit gap.",
  },
  application_package: {
    readiness_score: 65,
    ready_to_finalize: false,
    cover_letter_verified: false,
    question_count: 3,
    verified_question_count: 1,
    checklist: [],
  },
  communications: {
    recruiter_message: "Hi — I’m interested in the Senior Data Engineer role at ApplyAI Labs.",
    recruiter_message_verified: false,
    follow_up_message: "Hi — I wanted to follow up on my application.",
    follow_up_message_verified: false,
    policy: "CANDIDATE_REVIEW_REQUIRED",
  },
  portfolio_preview: {
    headline: "Senior data engineering leader",
    about: "Verified data platform leader focused on reliable analytics infrastructure.",
    target_context: "Senior Data Engineer",
    highlights: [
      {
        title: "Senior Data Engineering Manager",
        company: "Atlas Health",
        description: "Led a verified data engineering organization.",
        provenance: "USER_VERIFIED",
      },
    ],
    skills: ["Python", "SQL", "AWS"],
    safety: {
      policy: "VERIFIED_EVIDENCE_ONLY",
      message: "Verified evidence only.",
    },
  },
  interview: {
    ready: false,
    artifact_id: null,
    status: "NOT_STARTED",
    candidate_verified: false,
    content: null,
    starter_questions: [
      {
        focus: "Python",
        question: "Walk me through a concrete example where you used Python.",
      },
    ],
  },
  actions: {
    resume: "/resume/studio",
    career_memory: "/career",
    application: null,
    interview_task: "interview-prep",
  },
  safety: {
    evidence_policy: "VERIFIED_EVIDENCE_ONLY",
    external_action_policy: "CANDIDATE_REVIEW_REQUIRED",
  },
};

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CareerSystemPanel jobId="job-1" />
    </QueryClientProvider>,
  );
}

describe("CareerSystemPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(careerSystemApi.get).mockResolvedValue(snapshot);
    vi.mocked(careerSystemApi.saveCommunications).mockResolvedValue({
      ...snapshot,
      application_id: "application-1",
      application_status: "DRAFT",
      progress_score: 50,
      communications: {
        ...snapshot.communications,
        recruiter_message: `${snapshot.communications.recruiter_message} Happy to share more context.`,
        recruiter_message_verified: true,
        follow_up_message_verified: true,
      },
    });
    vi.mocked(api.applications.create).mockResolvedValue({ id: "application-1" } as Awaited<ReturnType<typeof api.applications.create>>);
    vi.mocked(api.careerV2.start).mockResolvedValue({
      id: "run-1",
      status: "COMPLETED",
    } as Awaited<ReturnType<typeof api.careerV2.start>>);
  });

  it("renders the complete job-search system without presenting progress as hiring probability", async () => {
    renderPanel();

    expect(await screen.findByRole("heading", { name: "One role. One complete application workspace." })).toBeDefined();
    expect(screen.getByText("30%")).toBeDefined();
    expect(screen.getByText(/not a hiring probability/i)).toBeDefined();
    expect(screen.getByText("78%")).toBeDefined();
    expect(screen.getByText("Kafka").textContent).toBe("Kafka");
    expect(screen.getByText("Senior data engineering leader")).toBeDefined();
    expect(screen.getByText(/concrete example where you used Python/i)).toBeDefined();
  });

  it("persists candidate-reviewed recruiter and follow-up messages", async () => {
    renderPanel();
    await screen.findByText("Recruiter outreach + follow-up");

    const recruiter = screen.getByLabelText("Recruiter message");
    fireEvent.change(recruiter, {
      target: {
        value: `${snapshot.communications.recruiter_message} Happy to share more context.`,
      },
    });

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole("button", { name: /save reviewed messages/i }));

    await waitFor(() => expect(careerSystemApi.saveCommunications).toHaveBeenCalledTimes(1));
    expect(careerSystemApi.saveCommunications).toHaveBeenCalledWith(
      "job-1",
      expect.objectContaining({
        recruiter_message_verified: true,
        follow_up_message_verified: true,
      }),
    );
    expect(successMock).toHaveBeenCalledWith("Recruiter outreach and follow-up saved");
  });

  it("starts the existing evidence-bound interview preparation task", async () => {
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Create full interview pack" }));

    await waitFor(() => expect(api.careerV2.start).toHaveBeenCalledWith("job-1", "interview-prep"));
    expect(successMock).toHaveBeenCalledWith("Job-specific interview preparation is ready");
  });
});
