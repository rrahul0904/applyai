import { describe, expect, it } from "vitest";
import { clerkPublishableKeyInstanceFingerprint } from "./clerk-instance";

describe("clerkPublishableKeyInstanceFingerprint", () => {
  it("matches the API hostname fingerprint contract", () => {
    expect(
      clerkPublishableKeyInstanceFingerprint(
        "pk_test_ZGVtby5jbGVyay5hY2NvdW50cy5kZXYk",
      ),
    ).toBe("2f2a1c73d57179de");
  });

  it("accepts live prefix with the same encoded instance", () => {
    expect(
      clerkPublishableKeyInstanceFingerprint(
        "pk_live_ZGVtby5jbGVyay5hY2NvdW50cy5kZXYk",
      ),
    ).toBe("2f2a1c73d57179de");
  });

  it("fails closed for missing or malformed keys", () => {
    expect(clerkPublishableKeyInstanceFingerprint(undefined)).toBe("");
    expect(clerkPublishableKeyInstanceFingerprint("not-a-clerk-key")).toBe("");
  });
});
