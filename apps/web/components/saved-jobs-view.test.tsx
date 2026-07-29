import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SavedJobsView } from "@/components/saved-jobs-view";
import { api } from "@/lib/api/client";

vi.mock("@/components/job-card", () => ({
  JobCard: ({ job }: { job: { title: string } }) => <div>{job.title}</div>,
}));

vi.mock("@/lib/api/client", () => ({
  api: {
    savedJobs: { list: vi.fn() },
  },
}));

function renderSavedJobs() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SavedJobsView />
    </QueryClientProvider>,
  );
}

describe("SavedJobsView", () => {
  beforeEach(() => {
    vi.mocked(api.savedJobs.list).mockResolvedValue([]);
  });

  it("renders an actionable empty state", async () => {
    renderSavedJobs();

    expect(await screen.findByText("No saved jobs yet")).toBeDefined();
    expect(screen.getByRole("link", { name: "Search jobs" }).getAttribute("href")).toBe("/jobs");
  });

  it("renders persisted saved jobs", async () => {
    vi.mocked(api.savedJobs.list).mockResolvedValue([
      {
        id: "job-1",
        title: "Senior Data Engineer",
        company_name: "ApplyAI Labs",
        location: "Boston, MA",
        work_mode: "HYBRID",
        minimum_compensation: 180000,
        maximum_compensation: 220000,
        compensation_provenance: "EMPLOYER_DISCLOSED",
        posted_at: "2026-07-20T00:00:00Z",
        last_seen_at: "2026-07-28T00:00:00Z",
        saved: true,
        data_origin: "GREENHOUSE_PUBLIC_API",
      },
    ]);

    renderSavedJobs();
    expect(await screen.findByText("Senior Data Engineer")).toBeDefined();
  });
});
