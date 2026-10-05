import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformApiError } from "@/lib/api/platform-client";
import { JobRadarView } from "./job-radar-view";

const api = vi.hoisted(() => ({
  profile: vi.fn(), saveProfile: vi.fn(), createScan: vi.fn(), getScan: vi.fn(),
}));

vi.mock("@/lib/api/platform-client", () => ({
  PlatformApiError: class PlatformApiError extends Error { constructor(public status: number, message: string) { super(message); } },
  platformApi: { jobRadar: api },
}));

function renderView() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><JobRadarView /></QueryClientProvider>);
}

describe("JobRadarView", () => {
  beforeEach(() => {
    api.profile.mockReset(); api.saveProfile.mockReset(); api.createScan.mockReset(); api.getScan.mockReset();
  });

  it("shows setup and empty results when a candidate has no Radar profile", async () => {
    api.profile.mockRejectedValue(new PlatformApiError(404, "Job Radar profile not found"));
    renderView();
    expect(await screen.findByText(/Set up a profile before your first scan/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save search profile" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Scan jobs" })).toHaveProperty("disabled", true);
  });

  it("saves a confirmed profile and shows canonical-store provider boundaries", async () => {
    const profile = { id: "profile-1", target_titles: ["Data analyst"], skills: ["SQL"], years_experience: null, seniority_preferences: [], preferred_locations: [], remote_policy: "ANY", salary_min: null, salary_currency: "USD" };
    api.profile.mockResolvedValue(profile);
    api.saveProfile.mockResolvedValue(profile);
    api.createScan.mockResolvedValue({ id: "scan-1", status: "COMPLETED", jobs_seen: 0, jobs_after_filter: 0, jobs_ranked: 0, error_code: null, error_detail: null, ai_reranking: "NOT_IMPLEMENTED", scheduled_delivery: "NOT_IMPLEMENTED", external_job_providers: "NOT_IMPLEMENTED", realtime_streaming: "NOT_IMPLEMENTED", matches: [] });
    renderView();
    expect(await screen.findByDisplayValue("Data analyst")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save search profile" }));
    await waitFor(() => expect(api.saveProfile).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "Scan jobs" }));
    expect(await screen.findByText(/External provider search, AI reranking, streaming and scheduled delivery are not enabled/)).toBeTruthy();
    expect(screen.getByText(/No matching jobs in this scan/)).toBeTruthy();
  });
});
