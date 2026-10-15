// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  signUp: vi.fn(),
  persist: vi.fn(),
  redirect: vi.fn((destination: string) => { throw new Error(`NEXT_REDIRECT:${destination}`); }),
}));

vi.mock("next/headers", () => ({
  headers: async () => new Headers({ origin: "https://applyai.example" }),
  cookies: vi.fn(),
}));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
vi.mock("@/lib/auth/supabase-http", () => ({
  supabaseConfigured: () => true,
  signUpWithPassword: mocks.signUp,
}));
vi.mock("@/lib/auth/supabase-session", () => ({ persistSupabaseSession: mocks.persist }));

import { signUpAction } from "./actions";

function credentials() {
  const form = new FormData();
  form.set("email", "Candidate@Example.com");
  form.set("password", "test-password");
  return form;
}

describe("Supabase signup redirects", () => {
  beforeEach(() => { mocks.signUp.mockReset(); mocks.persist.mockReset(); });

  it("takes an immediate authenticated signup to onboarding without swallowing Next redirect", async () => {
    const session = { access_token: "access", refresh_token: "refresh", expires_in: 3600 };
    mocks.signUp.mockResolvedValue(session);
    await expect(signUpAction(credentials())).rejects.toThrow("NEXT_REDIRECT:/onboarding");
    expect(mocks.persist).toHaveBeenCalledWith(session);
    expect(mocks.redirect).toHaveBeenCalledOnce();
    expect(mocks.signUp).toHaveBeenCalledWith("candidate@example.com", "test-password", "https://applyai.example/auth/callback");
  });

  it("shows confirmation instructions without creating a session when confirmation is required", async () => {
    mocks.signUp.mockResolvedValue({ user: { id: "candidate" } });
    await expect(signUpAction(credentials())).rejects.toThrow("NEXT_REDIRECT:/sign-up?check_email=1");
    expect(mocks.persist).not.toHaveBeenCalled();
  });

  it("keeps provider failures unauthenticated", async () => {
    mocks.signUp.mockRejectedValue(new Error("provider unavailable"));
    await expect(signUpAction(credentials())).rejects.toThrow("NEXT_REDIRECT:/sign-up?error=auth_error");
    expect(mocks.persist).not.toHaveBeenCalled();
  });
});
