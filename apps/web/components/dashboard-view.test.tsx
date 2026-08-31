import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardView } from "@/components/dashboard-view";
import { api } from "@/lib/api/client";
import { resumeShareApi } from "@/lib/api/resume-share";

const replace = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    api: {
      auth: { me: vi.fn() },
      profile: { get: vi.fn() },
      resumes: { list: vi.fn() },
      jobs: { search: vi.fn() },
      careerV2: { matches: vi.fn() },
      applications: { list: vi.fn() },
    },
  };
});

vi.mock("@/lib/api/resume-share", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/resume-share")>();
  return {
    ...original,
    resumeShareApi: { list: vi.fn() },
  };
});

function renderDashboard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <DashboardView />
    </QueryClientProvider>,
  );
}

function setBaseMocks() {
  vi.mocked(api.auth.me).mockResolvedValue({
    id: "user-1",
    email: "candidate@example.com",
    onboarding_completed: true,
  } as never);
  vi.mocked(api.profile.get).mockResolvedValue({
    target_roles: ["Data Engineering Manager"],
    work_modes: ["REMOTE"],
  } as never);
  vi.mocked(api.resumes.list).mockResolvedValue([
    {
      resume_id: "resume-1",
      filename: "resume.pdf",
      processing_status: "COMPLETED",
    },
  ] as never);
  vi.mocked(api.jobs.search).mockResolvedValue({
    items: [
      {
        id: "job-1",
        title: "Data Engineering Manager",
        company_name: "Acme Data",
        location: "Remote",
      },
    ],
    next_cursor: null,
  } as never);
  vi.mocked(api.careerV2.matches).mockResolvedValue({
    items: [
      {
        job_id: "job-1",
        deterministic_score: 82,
        ai_score: null,
        final_score: 82,
        fit_band: "STRONG",
        decision: "STRONG",
        confidence: "HIGH",
        engine_version: "test",
        factors: [],
        evidence: {
          matched_skills: ["Snowflake"],
          missing_skills: ["People leadership evidence"],
        },
        updated_at: "2026-08-31T12:00:00Z",
      },
    ],
  } as never);
  vi.mocked(api.applications.list).mockResolvedValue({ items: [] } as never);
  vi.mocked(resumeShareApi.list).mockResolvedValue([]);
}

describe("DashboardView first-value experience", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setBaseMocks();
  });

  it("centers the candidate home on one next action, jobs, and readiness", async () => {
    renderDashboard();

    expect(
      await screen.findByRole("heading", { name: "Your career workspace is ready." }),
    ).toBeDefined();
    expect(screen.getByRole("heading", { name: "Opportunities worth inspecting" })).toBeDefined();
    expect(await screen.findByText("Match 82/100")).toBeDefined();
    expect(screen.getByText("Snowflake")).toBeDefined();
    expect(screen.getByText("People leadership evidence")).toBeDefined();
    expect(screen.getByText(/preparation workflow completion, not employer interest/i)).toBeDefined();
  });

  it("prioritizes resume upload when no candidate evidence exists", async () => {
    vi.mocked(api.resumes.list).mockResolvedValue([]);

    renderDashboard();

    expect(
      await screen.findByRole("heading", {
        name: "Add your résumé before evaluating opportunities.",
      }),
    ).toBeDefined();
    const uploadLink = screen.getByRole("link", { name: /upload résumé/i });
    expect(uploadLink.getAttribute("href")).toBe("/resume");
  });

  it("surfaces tracked application engagement without converting it to hiring probability", async () => {
    vi.mocked(api.applications.list).mockResolvedValue({
      items: [
        {
          id: "application-1",
          current_status: "APPLIED",
          updated_at: "2026-08-31T12:00:00Z",
          job: {
            id: "job-1",
            title: "Data Engineering Manager",
            company_name: "Acme Data",
          },
        },
      ],
    } as never);
    vi.mocked(resumeShareApi.list).mockResolvedValue([
      {
        id: "share-1",
        public_token: "token",
        public_path: "/r/token",
        label: "Acme application",
        channel: "APPLICATION",
        status: "ACTIVE",
        active: true,
        always_current: true,
        allow_download: true,
        expires_at: null,
        application_id: "application-1",
        resume_version_id: "resume-1",
        filename: "resume.pdf",
        created_at: "2026-08-31T11:00:00Z",
        updated_at: "2026-08-31T12:00:00Z",
        job_id: "job-1",
        job_title: "Data Engineering Manager",
        company_name: "Acme Data",
        analytics: {
          views: 3,
          unique_viewers: 1,
          returning_viewers: 1,
          downloads: 0,
          link_clicks: 0,
          copies: 0,
          average_interest_score: 81,
          suspected_bot_events: 0,
          sessions: [
            {
              viewer: "Viewer abc123",
              session_key: "session-1",
              first_seen_at: "2026-08-31T11:30:00Z",
              last_seen_at: "2026-08-31T12:00:00Z",
              interest_score: 88,
              intent: "DEEP_READ",
              views: 3,
              dwell_ms: 120000,
              scroll_depth: 96,
              downloads: 0,
              link_clicks: 0,
              copies: 0,
            },
          ],
          timeline: [],
        },
        privacy: {
          raw_ip_stored: false,
          cross_link_fingerprinting: false,
          company_identity_inferred: false,
          engagement_is_hiring_probability: false,
        },
      },
    ]);

    renderDashboard();

    expect(await screen.findByText("Deep Read")).toBeDefined();
    expect(screen.getByText(/3 tracked views/i)).toBeDefined();
    expect(screen.getByText(/is not recruiter approval, interview selection, or hiring probability/i)).toBeDefined();
  });
});
