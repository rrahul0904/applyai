import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingView } from "@/components/onboarding-view";
import { api } from "@/lib/api/client";

const replace = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
}));

vi.mock("@/lib/api/client", () => ({
  api: {
    onboarding: { get: vi.fn(), update: vi.fn() },
    profile: { get: vi.fn(), save: vi.fn() },
    resumes: {
      list: vi.fn(),
      extraction: vi.fn(),
      upload: vi.fn(),
      confirm: vi.fn(),
    },
  },
}));

function renderOnboarding() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <OnboardingView />
    </QueryClientProvider>,
  );
}

const reviewedProfile = {
  id: "profile-1",
  user_id: "user-1",
  headline: "Verified candidate",
  current_title: "Principal Data Engineer",
  summary: null,
  years_experience: 8,
  target_roles: [],
  location_text: null,
  work_modes: [],
  minimum_compensation: null,
  experiences: [],
  education: [],
  skills: [],
};

const reviewResume = {
  id: "version-1",
  resume_id: "resume-1",
  filename: "resume.docx",
  content_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  file_size: 1234,
  upload_status: "UPLOADED",
  processing_status: "NEEDS_REVIEW",
  created_at: "2026-07-29T00:00:00Z",
};

const extraction = {
  id: "extraction-1",
  resume_version_id: "version-1",
  status: "NEEDS_REVIEW",
  error_code: null,
  created_at: "2026-07-29T00:00:01Z",
  structured_data: {
    basic_profile: { current_title: "Senior Data Engineer" },
    experiences: [{
      company_name: "Example Labs",
      title: "Senior Data Engineer",
      description: "Built data platforms",
    }],
    education: [{ institution: "Example University", degree: "BS", field_of_study: "CS" }],
    skills: [{ name: "Python" }, { name: "SQL" }],
  },
};

describe("OnboardingView", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    vi.mocked(api.profile.get).mockResolvedValue(null);
    vi.mocked(api.onboarding.update).mockImplementation(async (stage: string) => ({
      onboarding_stage: stage,
      onboarding_completed: stage === "COMPLETE",
    }));
    vi.mocked(api.profile.save).mockResolvedValue(reviewedProfile);
    vi.mocked(api.resumes.confirm).mockResolvedValue(reviewedProfile);
    vi.mocked(api.resumes.upload).mockResolvedValue(reviewResume);
  });

  it("restores a persisted extraction when refreshed on profile review", async () => {
    vi.mocked(api.onboarding.get).mockResolvedValue({
      onboarding_stage: "PROFILE_REVIEW",
      onboarding_completed: false,
    });
    vi.mocked(api.resumes.list).mockResolvedValue([reviewResume]);
    vi.mocked(api.resumes.extraction).mockResolvedValue(extraction);

    renderOnboarding();

    const currentTitle = await screen.findByLabelText("Current title") as HTMLInputElement;
    expect(currentTitle.value).toBe("Senior Data Engineer");
    expect(screen.getByDisplayValue("Example Labs")).toBeDefined();
    expect(screen.getByText("Python ×")).toBeDefined();
  });

  it("confirms resume-derived data instead of using generic profile save", async () => {
    vi.mocked(api.onboarding.get).mockResolvedValue({
      onboarding_stage: "PROFILE_REVIEW",
      onboarding_completed: false,
    });
    vi.mocked(api.resumes.list).mockResolvedValue([reviewResume]);
    vi.mocked(api.resumes.extraction).mockResolvedValue(extraction);

    renderOnboarding();
    const title = await screen.findByLabelText("Current title");
    fireEvent.change(title, { target: { value: "Principal Data Engineer" } });
    fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));

    await waitFor(() => expect(api.resumes.confirm).toHaveBeenCalledTimes(1));
    expect(api.resumes.confirm).toHaveBeenCalledWith(
      "resume-1",
      expect.objectContaining({
        current_title: "Principal Data Engineer",
        skills: expect.arrayContaining([
          expect.objectContaining({ name: "Python" }),
        ]),
      }),
    );
    expect(api.profile.save).not.toHaveBeenCalled();
    await waitFor(() => expect(api.onboarding.update).toHaveBeenCalledWith("TARGET_ROLES"));
  });

  it("keeps manual onboarding on normal profile persistence", async () => {
    vi.mocked(api.onboarding.get).mockResolvedValue({
      onboarding_stage: "PROFILE_REVIEW",
      onboarding_completed: false,
    });
    vi.mocked(api.resumes.list).mockResolvedValue([]);

    renderOnboarding();
    const title = await screen.findByLabelText("Current title");
    fireEvent.change(title, { target: { value: "Data Engineer" } });
    fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));

    await waitFor(() => expect(api.profile.save).toHaveBeenCalledTimes(1));
    expect(api.resumes.confirm).not.toHaveBeenCalled();
    await waitFor(() => expect(api.onboarding.update).toHaveBeenCalledWith("TARGET_ROLES"));
  });

  it("offers manual fallback after a failed resume parse", async () => {
    vi.mocked(api.onboarding.get).mockResolvedValue({
      onboarding_stage: "RESUME_PROCESSING",
      onboarding_completed: false,
    });
    vi.mocked(api.resumes.list).mockResolvedValue([{ ...reviewResume, processing_status: "FAILED" }]);
    vi.mocked(api.resumes.extraction).mockRejectedValue(new Error("not available"));

    renderOnboarding();

    expect(await screen.findByText("We couldn’t fully read this resume.")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Enter information manually" }));
    await waitFor(() => expect(api.onboarding.update).toHaveBeenCalledWith("PROFILE_REVIEW"));
  });
});
