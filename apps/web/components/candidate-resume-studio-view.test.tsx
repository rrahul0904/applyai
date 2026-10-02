import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CandidateResumeStudioView } from "./candidate-resume-studio-view";
import { platformApi } from "@/lib/api/platform-client";
import { toast } from "sonner";

vi.mock("@/lib/api/platform-client", () => ({ platformApi: { resumeStudio: {
  list: vi.fn(), create: vi.fn(), update: vi.fn(), export: vi.fn(),
} } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

function renderView() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><CandidateResumeStudioView /></QueryClientProvider>);
}

const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:resume");
const revokeObjectURL = vi.fn();

describe("Resume Studio PDF download", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.mocked(platformApi.resumeStudio.list).mockResolvedValue([{
      id: "resume-1", title: "Candidate resume", content: { summary: "Saved content" },
      status: "REVIEWED", version: 4, job_id: null, base_resume_version_id: null, updated_at: "2026-10-02",
    }]);
  });

  it("downloads decoded PDF bytes, reports overflow, and keeps editing separate", async () => {
    vi.mocked(platformApi.resumeStudio.export).mockResolvedValue({
      filename: "Candidate-resume.pdf", content: btoa("%PDF-1.7"), content_type: "application/pdf",
      content_encoding: "base64", version: 4,
      composition: { page_count: 2, page_status: "OVERFLOW_REQUIRES_REVIEW", extractable_text: true },
    });
    renderView();
    const pdf = await screen.findByRole("button", { name: "Download PDF" });
    fireEvent.change(screen.getByLabelText("Professional summary"), { target: { value: "Unsaved edits" } });
    fireEvent.click(pdf);
    await waitFor(() => expect(platformApi.resumeStudio.export).toHaveBeenCalledWith("resume-1", "pdf"));
    expect((await screen.findByRole("status")).textContent).toContain("2 pages. All content is included");
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("application/pdf");
    expect(blob.size).toBe(8);
    expect(platformApi.resumeStudio.update).not.toHaveBeenCalled();
    expect((screen.getByLabelText("Professional summary") as HTMLTextAreaElement).value).toBe("Unsaved edits");
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:resume");
  });

  it("keeps text download available and shows PDF errors", async () => {
    vi.mocked(platformApi.resumeStudio.export).mockRejectedValueOnce(new Error("Download text instead"));
    renderView();
    fireEvent.click(await screen.findByRole("button", { name: "Download PDF" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Download text instead"));
    vi.mocked(platformApi.resumeStudio.export).mockResolvedValueOnce({
      filename: "Candidate-resume.txt", content: "Saved content", content_type: "text/plain", version: 4,
    });
    fireEvent.click(screen.getByRole("button", { name: "Download text" }));
    await waitFor(() => expect(platformApi.resumeStudio.export).toHaveBeenCalledWith("resume-1", "txt"));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
    expect(screen.queryByRole("status")).toBeNull();
  });
});
