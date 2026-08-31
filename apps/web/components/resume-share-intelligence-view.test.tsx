import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ResumeShareIntelligenceView } from "@/components/resume-share-intelligence-view";
import { api } from "@/lib/api/client";
import { resumeShareApi, type ResumeShareSnapshot } from "@/lib/api/resume-share";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("jobId=job-1&label=Northstar%20%E2%80%94%20Manager&channel=application"),
}));

vi.mock("@/lib/api/client", () => ({
  api: { resumes: { list: vi.fn() } },
}));

vi.mock("@/lib/api/resume-share", () => ({
  resumeShareApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}));

const snapshot: ResumeShareSnapshot = {
  id: "share-1",
  public_token: "abcdefghijklmnopqrstuvwxyz123456",
  public_path: "/r/abcdefghijklmnopqrstuvwxyz123456",
  label: "Northstar — Manager",
  channel: "application",
  status: "ACTIVE",
  active: true,
  always_current: true,
  allow_download: true,
  expires_at: null,
  application_id: null,
  resume_version_id: "resume-v1",
  filename: "candidate.pdf",
  created_at: "2026-08-31T05:00:00Z",
  updated_at: "2026-08-31T05:00:00Z",
  job_id: "job-1",
  job_title: "Product Operations Manager",
  company_name: "Northstar Health",
  analytics: {
    views: 3,
    unique_viewers: 2,
    returning_viewers: 1,
    downloads: 1,
    link_clicks: 2,
    copies: 0,
    average_interest_score: 76,
    suspected_bot_events: 1,
    sessions: [
      {
        viewer: "Viewer abcdef12",
        session_key: "abcdef123456",
        first_seen_at: "2026-08-31T05:00:00Z",
        last_seen_at: "2026-08-31T05:05:00Z",
        interest_score: 88,
        intent: "DEEP_READ",
        views: 2,
        dwell_ms: 120000,
        scroll_depth: 95,
        downloads: 1,
        link_clicks: 1,
        copies: 0,
      },
    ],
    timeline: [
      {
        viewer: "Viewer abcdef12",
        event_type: "DOWNLOAD",
        value: null,
        target: null,
        occurred_at: "2026-08-31T05:05:00Z",
      },
    ],
  },
  privacy: {
    raw_ip_stored: false,
    cross_link_fingerprinting: false,
    company_identity_inferred: false,
    engagement_is_hiring_probability: false,
  },
};

function renderView() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ResumeShareIntelligenceView />
    </QueryClientProvider>,
  );
}

describe("ResumeShareIntelligenceView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.resumes.list).mockResolvedValue([
      {
        id: "resume-v1",
        resume_id: "resume-1",
        filename: "candidate.pdf",
        content_type: "application/pdf",
        file_size: 1024,
        upload_status: "UPLOADED",
        processing_status: "COMPLETED",
        created_at: "2026-08-31T04:00:00Z",
      },
    ]);
    vi.mocked(resumeShareApi.list).mockResolvedValue([snapshot]);
    vi.mocked(resumeShareApi.create).mockResolvedValue(snapshot);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("renders role-linked resume engagement without claiming viewer identity", async () => {
    renderView();

    expect(await screen.findByRole("heading", { name: /Know what happens after you share your resume/i })).toBeDefined();
    expect(await screen.findByText("Northstar Health · Product Operations Manager")).toBeDefined();
    expect(screen.getByText("Deep Read")).toBeDefined();
    expect(screen.getByText(/does not store raw viewer IP addresses/i)).toBeDefined();
    expect(screen.getByText(/never hiring probability/i)).toBeDefined();
    expect(screen.getByText("Viewer abcdef12")).toBeDefined();
  });

  it("prefills a job-specific smart link and creates it", async () => {
    renderView();
    const label = await screen.findByDisplayValue("Northstar — Manager");
    fireEvent.change(label, { target: { value: "Northstar follow-up" } });
    fireEvent.click(screen.getByRole("button", { name: /Create & copy link/i }));

    await waitFor(() => {
      expect(resumeShareApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          job_id: "job-1",
          label: "Northstar follow-up",
          channel: "application",
          always_current: true,
          allow_download: true,
        }),
      );
    });
  });
});
