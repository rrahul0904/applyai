import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const firstItem = {
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
};

describe("ApplicationsView", () => {
  beforeEach(() => {
    vi.mocked(api.applications.list).mockResolvedValue({
      items: [firstItem],
      next_cursor: null,
      returned: 1,
    });
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
    vi.mocked(api.applications.list).mockResolvedValue({
      items: [],
      next_cursor: null,
      returned: 0,
    });
    renderApplications();

    expect(await screen.findByText("No applications yet")).toBeDefined();
    expect(screen.getByRole("link", { name: "Explore jobs" }).getAttribute("href")).toBe("/jobs");
  });

  it("loads the next bounded page using the returned cursor", async () => {
    vi.mocked(api.applications.list)
      .mockResolvedValueOnce({ items: [firstItem], next_cursor: "cursor-2", returned: 1 })
      .mockResolvedValueOnce({
        items: [{
          ...firstItem,
          id: "application-2",
          job_id: "job-2",
          current_status: "INTERVIEW",
          job: {
            id: "job-2",
            title: "Data Platform Manager",
            company_name: "Example Labs",
            location: null,
          },
        }],
        next_cursor: null,
        returned: 1,
      });

    renderApplications();
    fireEvent.click(await screen.findByRole("button", { name: "Show more applications" }));

    expect(await screen.findByText("Data Platform Manager")).toBeDefined();
    await waitFor(() => expect(api.applications.list).toHaveBeenLastCalledWith(expect.anything(), "cursor-2"));
    expect(api.jobs.detail).not.toHaveBeenCalled();
  });
});
