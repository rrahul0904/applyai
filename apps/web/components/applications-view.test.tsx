import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApplicationsView } from "@/components/applications-view";
import { api } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  api: {
    applications: { board: vi.fn() },
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
  tracker: {
    deadline_at: "2026-08-01T17:00:00Z",
    interview_at: null,
    next_action_at: "2026-07-29T13:00:00Z",
    offer_minimum: null,
    offer_maximum: null,
    offer_currency: "USD",
    offer_notes: null,
    source_channel: "Referral",
    priority: "HIGH",
    updated_at: "2026-07-28T00:00:00Z",
  },
  overdue: false,
};

describe("ApplicationsView", () => {
  beforeEach(() => {
    vi.mocked(api.applications.board).mockResolvedValue({
      items: [firstItem],
      counts: { APPLIED: 1 },
      total: 1,
    });
  });

  it("renders the stage-first opportunity board without fetching each job detail", async () => {
    renderApplications();

    expect(await screen.findByText("Product Operations Manager")).toBeDefined();
    expect(screen.getByText("Northstar Health · Boston, MA")).toBeDefined();
    expect(screen.getByRole("heading", { name: "Applied" })).toBeDefined();
    expect(screen.getByText("High")).toBeDefined();
    expect(screen.getByText(/Referral/)).toBeDefined();

    await waitFor(() => expect(api.applications.board).toHaveBeenCalledTimes(1));
    expect(api.jobs.detail).not.toHaveBeenCalled();
  });

  it("renders the persisted opportunity empty state when no active pursuits exist", async () => {
    vi.mocked(api.applications.board).mockResolvedValue({
      items: [],
      counts: {},
      total: 0,
    });
    renderApplications();

    expect(await screen.findByText("No active opportunities yet")).toBeDefined();
    expect(screen.getByRole("link", { name: "Explore jobs" }).getAttribute("href")).toBe("/jobs");
  });

  it("surfaces overdue opportunities and offers in the board summary", async () => {
    vi.mocked(api.applications.board).mockResolvedValue({
      items: [
        { ...firstItem, overdue: true },
        {
          ...firstItem,
          id: "application-2",
          job_id: "job-2",
          current_status: "OFFER",
          job: {
            id: "job-2",
            title: "Data Platform Manager",
            company_name: "Example Labs",
            location: null,
          },
          tracker: {
            ...firstItem.tracker,
            priority: "MEDIUM",
            offer_minimum: 180000,
            offer_maximum: 210000,
          },
        },
      ],
      counts: { APPLIED: 1, OFFER: 1 },
      total: 2,
    });

    renderApplications();

    expect(await screen.findByText("2 opportunities")).toBeDefined();
    expect(screen.getByText("1 overdue deadlines")).toBeDefined();
    expect(screen.getByText("1 offers")).toBeDefined();
    expect(screen.getByText("Data Platform Manager")).toBeDefined();
  });
});
