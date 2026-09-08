"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import {
  buildGoogleAuthorizeUrl,
  newOAuthState,
  newPkceVerifier,
  revokeSupabaseSession,
  signInWithPassword,
  signUpWithPassword,
  SUPABASE_ACCESS_COOKIE,
  SUPABASE_OAUTH_STATE_COOKIE,
  SUPABASE_PKCE_VERIFIER_COOKIE,
  supabaseConfigured,
} from "@/lib/auth/supabase-http";
import {
  clearSupabaseSession,
  persistSupabaseSession,
} from "@/lib/auth/supabase-session";

function normalizedCredentials(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const password = String(formData.get("password") ?? "");
  if (!email.includes("@") || password.length < 8) {
    throw new Error("INVALID_CREDENTIAL_INPUT");
  }
  return { email, password };
}

function safeErrorCode(error: unknown) {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("Invalid login credentials")) return "invalid_credentials";
  if (message.includes("Email not confirmed")) return "email_not_confirmed";
  if (message.includes("User already registered")) return "already_registered";
  if (message.includes("Password should be")) return "weak_password";
  return "auth_error";
}

function originFromHeaders(incoming: Headers) {
  const explicit = incoming.get("origin");
  if (explicit?.startsWith("http://") || explicit?.startsWith("https://")) return explicit;
  const host = incoming.get("x-forwarded-host") ?? incoming.get("host");
  const protocol = incoming.get("x-forwarded-proto") ?? (host?.includes("localhost") ? "http" : "https");
  if (!host) throw new Error("AUTH_ORIGIN_UNAVAILABLE");
  return `${protocol}://${host}`;
}

function transientCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/auth",
    maxAge: 600,
  };
}

export async function signInAction(formData: FormData) {
  if (!supabaseConfigured()) redirect("/sign-in?error=auth_not_configured");
  const { email, password } = normalizedCredentials(formData);
  try {
    const session = await signInWithPassword(email, password);
    await persistSupabaseSession(session);
  } catch (error) {
    redirect(`/sign-in?error=${safeErrorCode(error)}`);
  }
  redirect("/dashboard");
}

export async function signUpAction(formData: FormData) {
  if (!supabaseConfigured()) redirect("/sign-up?error=auth_not_configured");
  const { email, password } = normalizedCredentials(formData);
  try {
    const result = await signUpWithPassword(email, password);
    if ("access_token" in result && result.access_token && result.refresh_token) {
      await persistSupabaseSession(result as Parameters<typeof persistSupabaseSession>[0]);
      redirect("/onboarding");
    }
  } catch (error) {
    redirect(`/sign-up?error=${safeErrorCode(error)}`);
  }
  redirect("/sign-up?check_email=1");
}

export async function googleSignInAction() {
  if (!supabaseConfigured()) redirect("/sign-in?error=auth_not_configured");
  const verifier = newPkceVerifier();
  const state = newOAuthState();
  const store = await cookies();
  store.set(SUPABASE_PKCE_VERIFIER_COOKIE, verifier, transientCookieOptions());
  store.set(SUPABASE_OAUTH_STATE_COOKIE, state, transientCookieOptions());
  const origin = originFromHeaders(await headers());
  redirect(
    buildGoogleAuthorizeUrl({
      redirectTo: `${origin}/auth/callback`,
      verifier,
      state,
    }),
  );
}

export async function signOutAction() {
  const store = await cookies();
  const accessToken = store.get(SUPABASE_ACCESS_COOKIE)?.value;
  if (accessToken) {
    await revokeSupabaseSession(accessToken).catch(() => undefined);
  }
  await clearSupabaseSession();
  redirect("/");
}
