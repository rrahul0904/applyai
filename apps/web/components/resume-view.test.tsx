import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResumeView } from "@/components/resume-view";
import { api } from "@/lib/api/client";

const { successMock, errorMock } = vi.hoisted(() => ({
  successMock: vi.fn(),
  errorMock: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: successMock, error: errorMock },
}));

vi.mock("@/lib/api/client", () => ({
  api: {
    resumes: { list: vi.fn(), upload: vi.fn() },
  },
}));

function renderResume() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ResumeView />
    </QueryClientProvider>,
  );
}

const baseResume = {
  id: "version-1",
  resume_id: "resume-1",
  filename: "candidate.docx",
  content_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  file_size: 2048,
  upload_status: "UPLOADED",
  processing_status: "QUEUED",
  created_at: "2026-07-29T00:00:00Z",
};

describe("ResumeView", () => {
  beforeEach(() => {
    successMock.mockReset();
    errorMock.mockReset();
    vi.mocked(api.resumes.list).mockResolvedValue([baseResume]);
    vi.mocked(api.resumes.upload).mockResolvedValue(baseResume);
  });

  it.each(["QUEUED", "PROCESSING", "COMPLETED"])("renders %s state", async (state) => {
    vi.mocked(api.resumes.list).mockResolvedValue([{ ...baseResume, processing_status: state }]);
    renderResume();
    expect(await screen.findByText(state.charAt(0) + state.slice(1).toLowerCase())).toBeDefined();
  });

  it("offers review when extraction needs candidate confirmation", async () => {
    vi.mocked(api.resumes.list).mockResolvedValue([{ ...baseResume, processing_status: "NEEDS_REVIEW" }]);
    renderResume();
    const link = await screen.findByRole("link", { name: "Review extracted profile" });
    expect(link.getAttribute("href")).toBe("/onboarding");
  });

  it("keeps the candidate unblocked after parser failure", async () => {
    vi.mocked(api.resumes.list).mockResolvedValue([{ ...baseResume, processing_status: "FAILED" }]);
    renderResume();
    expect(await screen.findByText(/Upload another version or continue editing your profile manually/)).toBeDefined();
    expect(screen.getByText("Upload resume")).toBeDefined();
  });

  it("passes a selected file to the upload boundary", async () => {
    renderResume();
    await screen.findByText("candidate.docx");
    const file = new File(["resume"], "replacement.pdf", { type: "application/pdf" });
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).not.toBeNull();
    fireEvent.change(input!, { target: { files: [file] } });
    await waitFor(() => expect(api.resumes.upload).toHaveBeenCalledWith(file));
    await waitFor(() => expect(successMock).toHaveBeenCalledWith("Resume uploaded"));
  });

  it("renders an empty state when no resume exists", async () => {
    vi.mocked(api.resumes.list).mockResolvedValue([]);
    renderResume();
    expect(await screen.findByText("No resume uploaded")).toBeDefined();
  });
});
