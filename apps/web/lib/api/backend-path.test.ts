import { describe, expect, it } from "vitest";
import { MAX_PROXY_BODY_BYTES, safeBackendPath } from "@/lib/api/backend-path";

describe("backend path guard", () => {
  it("allows intended API path segments", () => {
    expect(safeBackendPath(["applications", "123e4567-e89b-12d3-a456-426614174000", "status"]))
      .toBe("applications/123e4567-e89b-12d3-a456-426614174000/status");
    expect(safeBackendPath(["resumes", "upload-intents"]))
      .toBe("resumes/upload-intents");
  });

  it("rejects traversal, dot segments, encoded separators, and empty paths", () => {
    expect(safeBackendPath([])).toBeNull();
    expect(safeBackendPath(["..", "admin"])).toBeNull();
    expect(safeBackendPath(["jobs", "."])).toBeNull();
    expect(safeBackendPath(["jobs", "%2Fetc%2Fpasswd"])).toBeNull();
    expect(safeBackendPath(["jobs", "id?admin=true"])).toBeNull();
  });

  it("keeps ordinary BFF bodies below the direct-upload boundary", () => {
    expect(MAX_PROXY_BODY_BYTES).toBe(1024 * 1024);
  });
});
