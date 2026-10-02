// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("./supabase-http", () => ({
  SUPABASE_ACCESS_COOKIE: "applyai_sb_access",
  SUPABASE_REFRESH_COOKIE: "applyai_sb_refresh",
  supabaseConfigured: () => true,
  accessTokenNeedsRefresh: (token: string) => token === "expired",
  refreshSupabaseToken: mocks.refresh,
}));

import { refreshSupabaseSessionProxy } from "./supabase-proxy";

function request(access = "expired") {
  return new NextRequest("https://applyai.example/dashboard", {
    headers: { cookie: `applyai_sb_access=${access}; applyai_sb_refresh=old-refresh` },
  });
}

describe("Supabase proxy refresh", () => {
  beforeEach(() => { mocks.refresh.mockReset(); });

  it("forwards rotated cookies to this request and persists them for the next request", async () => {
    mocks.refresh.mockResolvedValue({ access_token: "new-access", refresh_token: "new-refresh", expires_in: 3600 });
    const incoming = request();
    const response = await refreshSupabaseSessionProxy(incoming);
    expect(response.headers.get("x-middleware-request-cookie")).toContain("applyai_sb_access=new-access");
    expect(response.headers.get("x-middleware-request-cookie")).toContain("applyai_sb_refresh=new-refresh");
    expect(response.headers.get("x-middleware-request-cookie")).not.toContain("old-refresh");
    expect(response.cookies.get("applyai_sb_access")?.value).toBe("new-access");
    expect(response.cookies.get("applyai_sb_refresh")?.value).toBe("new-refresh");
  });

  it("removes stale credentials from both the current request and browser on rejection", async () => {
    mocks.refresh.mockRejectedValue(new Error("invalid refresh token"));
    const incoming = request();
    const response = await refreshSupabaseSessionProxy(incoming);
    expect(incoming.cookies.get("applyai_sb_access")).toBeUndefined();
    expect(incoming.cookies.get("applyai_sb_refresh")).toBeUndefined();
    expect(response.headers.get("x-middleware-request-cookie") ?? "").not.toContain("old-refresh");
    expect(response.cookies.get("applyai_sb_access")?.value).toBe("");
  });

  it("does not rotate an access token that is still current", async () => {
    const response = await refreshSupabaseSessionProxy(request("current"));
    expect(mocks.refresh).not.toHaveBeenCalled();
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
