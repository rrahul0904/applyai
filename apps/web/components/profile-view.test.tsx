import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfileView } from "@/components/profile-view";
import { api } from "@/lib/api/client";

const { successMock, errorMock } = vi.hoisted(() => ({
  successMock: vi.fn(),
  errorMock: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: successMock, error: errorMock },
}));

vi.mock("@/lib/api/client", () => ({
  api: { profile: { get: vi.fn(), save: vi.fn() } },
}));

const profile = {
  id: "profile-1",
  user_id: "user-1",
  headline: "Data platform leader",
  current_title: "Senior Data Engineer",
  summary: "Builds reliable platforms.",
  years_experience: 8,
  target_roles: ["Staff Data Engineer"],
  location_text: "Boston, MA",
  work_modes: ["REMOTE"],
  minimum_compensation: 180000,
  experiences: [{
    id: "experience-1",
    company_name: "Example Labs",
    title: "Senior Data Engineer",
    description: "Built production systems",
    start_date: null,
    end_date: null,
    provenance: "USER_VERIFIED",
  }],
  education: [],
  skills: [{ id: "skill-1", name: "Python", provenance: "USER_VERIFIED" }],
};

function renderProfile() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ProfileView />
    </QueryClientProvider>,
  );
}

describe("ProfileView", () => {
  beforeEach(() => {
    successMock.mockReset();
    errorMock.mockReset();
    vi.mocked(api.profile.get).mockResolvedValue(profile);
    vi.mocked(api.profile.save).mockImplementation(async (payload) => ({
      ...profile,
      ...payload,
      experiences: payload.experiences ?? [],
      education: payload.education ?? [],
      skills: payload.skills ?? [],
    }));
  });

  it("loads persisted candidate profile and preferences", async () => {
    renderProfile();
    expect(await screen.findByDisplayValue("Senior Data Engineer")).toBeDefined();
    expect(screen.getByDisplayValue("Boston, MA")).toBeDefined();
    expect(screen.getByText("Python ×")).toBeDefined();
    expect(screen.getByText("Primary · Staff Data Engineer")).toBeDefined();
  });

  it("persists profile edits through the API boundary", async () => {
    renderProfile();
    const title = await screen.findByLabelText("Current title");
    fireEvent.change(title, { target: { value: "Principal Data Engineer" } });
    fireEvent.change(screen.getByLabelText("Minimum compensation (USD)"), {
      target: { value: "200000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(api.profile.save).toHaveBeenCalledTimes(1));
    expect(api.profile.save).toHaveBeenCalledWith(
      expect.objectContaining({
        current_title: "Principal Data Engineer",
        minimum_compensation: 200000,
        target_roles: ["Staff Data Engineer"],
        work_modes: ["REMOTE"],
      }),
    );
    expect(successMock).toHaveBeenCalledWith("Profile saved");
  });

  it("adds structured skills and roles instead of freeform profile blobs", async () => {
    renderProfile();
    await screen.findByDisplayValue("Senior Data Engineer");

    fireEvent.change(screen.getByLabelText("Add skill"), { target: { value: "PostgreSQL" } });
    fireEvent.click(screen.getByRole("button", { name: "Add skill" }));
    fireEvent.change(screen.getByLabelText("Add target role"), { target: { value: "Data Platform Lead" } });
    fireEvent.click(screen.getByRole("button", { name: "Add role" }));
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(api.profile.save).toHaveBeenCalled());
    expect(api.profile.save).toHaveBeenLastCalledWith(
      expect.objectContaining({
        skills: expect.arrayContaining([expect.objectContaining({ name: "PostgreSQL" })]),
        target_roles: ["Staff Data Engineer", "Data Platform Lead"],
      }),
    );
  });
});
