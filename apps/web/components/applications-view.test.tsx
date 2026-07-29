import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApplicationsView } from "@/components/applications-view";
import { api } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  api: {
    applications: { list: vi.fn() },
    jobs: { detail: vi.fn() },
  },
}));

function renderApplications() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ApplicationsView />
    </QueryClientProvider>,
  );
}

describe("ApplicationsView", () => {
  beforeEach(() => {
    vi.mocked(api.applications.list).mockResolvedValue([
      {
        id: "application-1",
        job_id: "job-1",
        current_status: "APPLIED",
        created_at: "2026-07-20T00:00:00Z",
        updated_at: "2026-07-28T00:00:00Z",
        job: {
          id: "job-1",
          title: "Product Operations Manager",
          company_name: "Northstar Health",
          location: "Boston, MA",
        },
      },
    ]);
  });

  it("renders list-summary data without fetching each job detail", async () => {
    renderApplications();

    expect(await screen.findByText("Product Operations Manager")).toBeDefined();
    expect(screen.getByText("Northstar Health · Boston, MA")).toBeDefined();
    expect(screen.getByText("Applied")).toBeDefined();

    await waitFor(() => expect(api.applications.list).toHaveBeenCalledTimes(1));
    expect(api.jobs.detail).not.toHaveBeenCalled();
  });

  it("renders the persisted empty state when no applications exist", async () => {
    vi.mocked(api.applications.list).mockResolvedValue([]);
    renderApplications();

    expect(await screen.findByText("No applications yet")).toBeDefined();
    expect(screen.getByRole("link", { name: "Explore jobs" }).getAttribute("href")).toBe("/jobs");
  });
});
