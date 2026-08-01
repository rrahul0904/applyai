import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { JobDetailView } from "@/components/job-detail-view";
import { api } from "@/lib/api/client";

const { pushMock, successMock, errorMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: successMock,
    error: errorMock,
  },
}));

vi.mock("@/lib/api/client", () => ({
  api: {
    jobs: { detail: vi.fn() },
    savedJobs: { save: vi.fn(), unsave: vi.fn() },
    applications: { create: vi.fn() },
  },
}));

const job: Awaited<ReturnType<typeof api.jobs.detail>> = {
  id: "job-1",
  title: "Senior Data Engineer",
  company_name: "ApplyAI Labs",
  data_origin: "GREENHOUSE_PUBLIC_API",
  location: "Boston, MA",
  work_mode: "HYBRID",
  employment_type: "FULL_TIME",
  seniority: "SENIOR",
  status: "ACTIVE",
  minimum_compensation: 180000,
  maximum_compensation: 220000,
  compensation_provenance: "SOURCE_REPORTED",
  description: "Build reliable data products.",
  requirements: ["Python", "PostgreSQL"],
  skills: ["Python", "SQL"],
  saved: false,
  posted_at: "2026-07-20T00:00:00Z",
  last_seen_at: "2026-07-28T00:00:00Z",
  source_url: "https://example.com/jobs/job-1",
};

function renderJobDetail() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <JobDetailView jobId="job-1" />
    </QueryClientProvider>,
  );
}

describe("JobDetailView", () => {
  beforeEach(() => {
    vi.mocked(api.jobs.detail).mockResolvedValue(job);
    vi.mocked(api.savedJobs.save).mockResolvedValue(undefined);
    vi.mocked(api.savedJobs.unsave).mockResolvedValue(undefined);
    vi.mocked(api.applications.create).mockResolvedValue({ id: "application-1" } as Awaited<ReturnType<typeof api.applications.create>>);
  });

  it("renders canonical job details from the API", async () => {
    renderJobDetail();

    expect(await screen.findByRole("heading", { name: "Senior Data Engineer" })).toBeDefined();
    expect(screen.getAllByText("ApplyAI Labs").length).toBeGreaterThan(0);
    expect(screen.getByText("Boston, MA")).toBeDefined();
    expect(screen.getByText("Build reliable data products.")).toBeDefined();
    expect(screen.getByRole("link", { name: "Open source listing" }).getAttribute("href")).toBe(job.source_url);
  });

  it("persists a saved job through the real mutation boundary", async () => {
    renderJobDetail();

    fireEvent.click(await screen.findByRole("button", { name: /save job/i }));

    await waitFor(() => expect(api.savedJobs.save).toHaveBeenCalledWith("job-1"));
    expect(successMock).toHaveBeenCalledWith("Job saved");
  });

  it("creates an application and routes to its workspace", async () => {
    renderJobDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Track application" }));

    await waitFor(() => expect(api.applications.create).toHaveBeenCalledWith("job-1"));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/applications/application-1"));
  });
});
