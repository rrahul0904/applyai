import { describe, expect, it } from "vitest";
import { supabaseProjectFingerprint } from "./supabase-instance";

describe("supabaseProjectFingerprint", () => {
  it("matches the API project hostname fingerprint contract", () => {
    expect(
      supabaseProjectFingerprint("https://applyai-test.supabase.co"),
    ).toBe("579ad99e95a603e1");
  });

  it("normalizes project hostname casing", () => {
    expect(
      supabaseProjectFingerprint("https://APPLYAI-TEST.SUPABASE.CO/"),
    ).toBe("579ad99e95a603e1");
  });

  it("fails closed for missing or malformed project URLs", () => {
    expect(supabaseProjectFingerprint(undefined)).toBe("");
    expect(supabaseProjectFingerprint("not-a-url")).toBe("");
  });
});
