import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

const version = {
  id: "version-1",
  resume_id: "resume-1",
  filename: "resume.pdf",
  content_type: "application/pdf",
  file_size: 6,
  upload_status: "UPLOADED",
  processing_status: "QUEUED",
  created_at: "2026-07-29T00:00:00Z",
};

describe("resume API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uploads file bytes directly to the presigned S3 URL", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        upload_mode: "DIRECT_S3",
        resume_id: "resume-1",
        resume_version_id: "version-1",
        upload_url: "https://s3.example.test/presigned",
        upload_headers: {
          "content-type": "application/pdf",
          "x-amz-server-side-encryption": "AES256",
        },
        expires_in_seconds: 900,
      }))
      .mockResolvedValueOnce({ ok: true, status: 200 } as Response)
      .mockResolvedValueOnce(jsonResponse(version));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["resume"], "resume.pdf", { type: "application/pdf" });
    const result = await api.resumes.upload(file);

    expect(result.id).toBe("version-1");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/backend/resumes/upload-intents");
    expect(fetchMock.mock.calls[1][0]).toBe("https://s3.example.test/presigned");
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({
      method: "PUT",
      body: file,
      headers: {
        "content-type": "application/pdf",
        "x-amz-server-side-encryption": "AES256",
      },
    }));
    expect(fetchMock.mock.calls[2][0]).toBe(
      "/api/backend/resumes/versions/version-1/upload-complete",
    );

    const intentBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(intentBody).toEqual({
      filename: "resume.pdf",
      content_type: "application/pdf",
      file_size: file.size,
    });
  });

  it("uses multipart proxy upload only when the API explicitly returns PROXY", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        upload_mode: "PROXY",
        resume_id: null,
        resume_version_id: null,
        upload_url: null,
        upload_headers: {},
        expires_in_seconds: null,
      }))
      .mockResolvedValueOnce(jsonResponse(version, 201));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["resume"], "resume.pdf", { type: "application/pdf" });
    await api.resumes.upload(file);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/backend/resumes");
    const options = fetchMock.mock.calls[1][1] as RequestInit;
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
  });

  it("does not call upload-complete when the direct S3 PUT fails", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        upload_mode: "DIRECT_S3",
        resume_id: "resume-1",
        resume_version_id: "version-1",
        upload_url: "https://s3.example.test/presigned",
        upload_headers: { "content-type": "application/pdf" },
        expires_in_seconds: 900,
      }))
      .mockResolvedValueOnce({ ok: false, status: 403 } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["resume"], "resume.pdf", { type: "application/pdf" });
    await expect(api.resumes.upload(file)).rejects.toMatchObject({ code: "UPLOAD_FAILED" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
