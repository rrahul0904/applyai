// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";

import { backendReadiness } from "./backend-readiness";

const readyPayload = {
  status: "ready",
  database_reachable: true,
  operator_auth_configured: false,
  operator_auth_location: "database",
  storage_configured: true,
  background_worker_configured: true,
  auth_provider: "supabase",
  clerk_instance_fingerprint: "",
  supabase_project_fingerprint: "project-123",
};

describe("API readiness contract", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("counts a well-formed backend response as reachable while preserving unhealthy component checks", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ...readyPayload, database_reachable: false }),
      }),
    );

    await expect(backendReadiness("https://api.example.test")).resolves.toMatchObject({
      reachable: true,
      contractValid: true,
      upstreamStatus: 200,
      failureClass: null,
      databaseReachable: false,
      authProvider: "supabase",
    });
  });

  it("reports upstream status and does not call a non-2xx API reachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503 }),
    );

    await expect(backendReadiness("https://api.example.test")).resolves.toMatchObject({
      reachable: false,
      contractValid: false,
      upstreamStatus: 503,
      failureClass: "UPSTREAM_NON_2XX",
    });
  });

  it("fails closed when a 2xx response does not match the readiness contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ message: "wrong upstream" }),
      }),
    );

    await expect(backendReadiness("https://api.example.test")).resolves.toMatchObject({
      reachable: false,
      contractValid: false,
      upstreamStatus: 200,
      failureClass: "INVALID_READINESS_PAYLOAD",
    });
  });

  it("reports an unreachable API without exposing upstream error details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private network detail")));

    const result = await backendReadiness("https://api.example.test");

    expect(result).toMatchObject({
      reachable: false,
      upstreamStatus: null,
      failureClass: "UPSTREAM_UNREACHABLE",
    });
    expect(JSON.stringify(result)).not.toContain("private network detail");
  });
});
