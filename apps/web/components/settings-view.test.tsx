import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsView } from "@/components/settings-view";
import { api } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  api: {
    auth: { me: vi.fn() },
    profile: { get: vi.fn() },
  },
}));

function renderSettings() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsView />
    </QueryClientProvider>,
  );
}

describe("SettingsView", () => {
  beforeEach(() => {
    vi.mocked(api.auth.me).mockResolvedValue({
      id: "user-1",
      email: "candidate@example.test",
      first_name: "Candidate",
      last_name: null,
      account_status: "ACTIVE",
      onboarding_completed: true,
      onboarding_stage: "COMPLETE",
    });
    vi.mocked(api.profile.get).mockResolvedValue({
      id: "profile-1",
      user_id: "user-1",
      headline: "Data engineer",
      current_title: "Senior Data Engineer",
      summary: null,
      years_experience: 8,
      target_roles: ["Staff Data Engineer", "Data Platform Lead"],
      location_text: "Boston, MA",
      work_modes: ["REMOTE", "HYBRID"],
      minimum_compensation: 180000,
      experiences: [],
      education: [],
      skills: [],
    });
  });

  it("shows persisted account and profile state alongside customer controls", async () => {
    renderSettings();
    expect(await screen.findByText("candidate@example.test")).toBeDefined();
    expect(screen.getByText("ACTIVE")).toBeDefined();
    expect(screen.getByText("Complete")).toBeDefined();
    expect(screen.getByText("Staff Data Engineer, Data Platform Lead")).toBeDefined();
    expect(screen.getByText("Boston, MA")).toBeDefined();
    expect(screen.getByText("REMOTE, HYBRID")).toBeDefined();
    expect(screen.getByRole("heading", { name: "Alerts" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Plan" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Your data" })).toBeDefined();
  });

  it("links preferences, alerts and plan to their customer workspaces", async () => {
    renderSettings();
    expect((await screen.findByRole("link", { name: "Edit profile" })).getAttribute("href")).toBe("/profile");
    expect(screen.getByRole("link", { name: "Manage alerts" }).getAttribute("href")).toBe("/alerts");
    expect(screen.getByRole("link", { name: "View plan" }).getAttribute("href")).toBe("/billing");
  });

  it("keeps privacy export and deletion controls easy to understand", async () => {
    renderSettings();
    expect(await screen.findByText(/Download a copy of your ApplyAI data/)).toBeDefined();
    expect(screen.getByRole("button", { name: "Download my data" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Delete my data" })).toBeDefined();
  });
});
