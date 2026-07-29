import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApplicationDetailView } from "@/components/application-detail-view";
import { api } from "@/lib/api/client";

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
    applications: {
      detail: vi.fn(),
      updateStatus: vi.fn(),
      addNote: vi.fn(),
      deleteNote: vi.fn(),
    },
    jobs: { detail: vi.fn() },
  },
}));

const application = {
  id: "application-1",
  job_id: "job-1",
  current_status: "APPLIED",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-28T00:00:00Z",
  events: [
    {
      id: "event-1",
      from_status: null,
      to_status: "PREPARING",
      created_at: "2026-07-20T00:00:00Z",
    },
    {
      id: "event-2",
      from_status: "PREPARING",
      to_status: "APPLIED",
      created_at: "2026-07-21T00:00:00Z",
    },
  ],
  notes: [
    {
      id: "note-1",
      body: "Recruiter follow-up on Friday",
      created_at: "2026-07-22T00:00:00Z",
      updated_at: "2026-07-22T00:00:00Z",
    },
  ],
} as Awaited<ReturnType<typeof api.applications.detail>>;

const job = {
  id: "job-1",
  title: "Senior Data Engineer",
  company_name: "ApplyAI Labs",
  data_origin: "GREENHOUSE_PUBLIC_API",
  location: "Boston, MA",
  work_mode: "HYBRID",
  employment_type: "FULL_TIME",
  seniority: "SENIOR",
  minimum_compensation: 180000,
  maximum_compensation: 220000,
  compensation_provenance: "EMPLOYER_DISCLOSED",
  description: "Build reliable data products.",
  requirements: [],
  skills: [],
  saved: true,
  posted_at: "2026-07-20T00:00:00Z",
  last_seen_at: "2026-07-28T00:00:00Z",
  source_url: "https://example.com/jobs/job-1",
  status: "ACTIVE",
} as Awaited<ReturnType<typeof api.jobs.detail>>;

function renderApplicationDetail() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ApplicationDetailView applicationId="application-1" />
    </QueryClientProvider>,
  );
}

describe("ApplicationDetailView", () => {
  beforeEach(() => {
    vi.mocked(api.applications.detail).mockResolvedValue(application);
    vi.mocked(api.jobs.detail).mockResolvedValue(job);
    vi.mocked(api.applications.updateStatus).mockResolvedValue({
      ...application,
      current_status: "INTERVIEW",
    });
    vi.mocked(api.applications.addNote).mockResolvedValue({
      id: "note-2",
      body: "Send portfolio",
      created_at: "2026-07-28T00:00:00Z",
      updated_at: "2026-07-28T00:00:00Z",
    });
    vi.mocked(api.applications.deleteNote).mockResolvedValue(undefined);
  });

  it("renders immutable timeline and persisted notes", async () => {
    renderApplicationDetail();

    expect(await screen.findByRole("heading", { name: "Senior Data Engineer" })).toBeDefined();
    expect(screen.getByText("Preparing → Applied")).toBeDefined();
    expect(screen.getByText("Recruiter follow-up on Friday")).toBeDefined();
  });

  it("persists a status change", async () => {
    renderApplicationDetail();

    const status = await screen.findByLabelText("Application status");
    fireEvent.change(status, { target: { value: "INTERVIEW" } });

    await waitFor(() => expect(api.applications.updateStatus).toHaveBeenCalledWith("application-1", "INTERVIEW"));
    expect(successMock).toHaveBeenCalledWith("Application status updated");
  });

  it("adds and deletes private notes through application mutations", async () => {
    renderApplicationDetail();

    const note = await screen.findByLabelText("Add a private note");
    fireEvent.change(note, { target: { value: "  Send portfolio  " } });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));

    await waitFor(() => expect(api.applications.addNote).toHaveBeenCalledWith("application-1", "Send portfolio"));
    expect(successMock).toHaveBeenCalledWith("Note added");

    fireEvent.click(screen.getByRole("button", { name: "Delete note" }));
    await waitFor(() => expect(api.applications.deleteNote).toHaveBeenCalledWith("application-1", "note-1"));
  });
});
