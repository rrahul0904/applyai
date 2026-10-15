// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";

import { authInstanceMatches, backendReadiness } from "./backend-readiness";

const readyPayload = {
  status: "ready",
  database_reachable: true,
  database_migrations_current: true,
  storage_reachable: true,
  auth_configured: true,
  auth_instance_match: true,
  operator_auth_configured: false,
  operator_auth_location: "database",
  storage_configured: true,
  task_queue_configured: true,
  background_worker_configured: true,
  background_worker_healthy: true,
  deployment_sha: "abc123",
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
      databaseMigrationsCurrent: true,
      authProvider: "supabase",
      deploymentSha: "abc123",
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

  it("fails closed for malformed JSON, missing fields, and an unsupported auth provider", async () => {
    const malformed = await backendReadinessWithPayload({ json: async () => { throw new Error("bad json"); } });
    const missing = await backendReadinessWithPayload({
      json: async () => ({ ...readyPayload, task_queue_configured: undefined }),
    });
    const wrongProvider = await backendReadinessWithPayload({
      json: async () => ({ ...readyPayload, auth_provider: "unknown-provider" }),
    });

    for (const result of [malformed, missing, wrongProvider]) {
      expect(result).toMatchObject({
        reachable: false,
        contractValid: false,
        failureClass: "INVALID_READINESS_PAYLOAD",
      });
    }
  });

  it("classifies missing configuration and mismatched Supabase instances", async () => {
    await expect(backendReadiness(undefined)).resolves.toMatchObject({
      reachable: false,
      failureClass: "API_NOT_CONFIGURED",
    });
    expect(authInstanceMatches("project-a", "project-b")).toBe(false);
    expect(authInstanceMatches("project-a", "project-a")).toBe(true);
    expect(authInstanceMatches("", "project-a")).toBe(false);
  });

  it.each([500, 503])("classifies HTTP %i as a non-ready upstream", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status }));

    await expect(backendReadiness("https://api.example.test")).resolves.toMatchObject({
      reachable: false,
      contractValid: false,
      upstreamStatus: status,
      failureClass: "UPSTREAM_NON_2XX",
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

  it("classifies request timeouts as unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("timed out", "TimeoutError")));

    await expect(backendReadiness("https://api.example.test")).resolves.toMatchObject({
      reachable: false,
      upstreamStatus: null,
      failureClass: "UPSTREAM_UNREACHABLE",
    });
  });
});

async function backendReadinessWithPayload(response: { json: () => Promise<unknown> }) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, ...response }));
  return backendReadiness("https://api.example.test");
}
