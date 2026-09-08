import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";
import { supabaseConfigured } from "@/lib/auth/supabase-http";
import { getValidatedSupabaseSession } from "@/lib/auth/supabase-session";

export const DEV_USER_COOKIE = "applyai_dev_user";

export type ApplyAISession =
  | { kind: "supabase"; authenticated: true; email: string }
  | { kind: "clerk"; authenticated: true; email: null }
  | { kind: "dev-test"; authenticated: true; email: string }
  | { kind: "none"; authenticated: false; email: null };

export function devAuthEnabled() {
  const enabled = process.env.DEV_AUTH_ENABLED === "true";
  if (process.env.APP_ENV === "production" && enabled) {
    throw new Error("Development authentication cannot run in production");
  }
  return enabled;
}

export async function getApplyAISession(): Promise<ApplyAISession> {
  if (devAuthEnabled()) {
    const email = (await cookies()).get(DEV_USER_COOKIE)?.value;
    return email
      ? { kind: "dev-test", authenticated: true, email }
      : { kind: "none", authenticated: false, email: null };
  }

  if (supabaseConfigured()) {
    const session = await getValidatedSupabaseSession();
    const email = session?.user.email?.trim().toLowerCase();
    return session && email
      ? { kind: "supabase", authenticated: true, email }
      : { kind: "none", authenticated: false, email: null };
  }

  if (
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
    process.env.CLERK_SECRET_KEY
  ) {
    const { userId } = await auth();
    return userId
      ? { kind: "clerk", authenticated: true, email: null }
      : { kind: "none", authenticated: false, email: null };
  }
  return { kind: "none", authenticated: false, email: null };
}

export async function getApplyAIAccessToken(): Promise<string | null> {
  if (supabaseConfigured()) {
    return (await getValidatedSupabaseSession())?.accessToken ?? null;
  }
  if (
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
    process.env.CLERK_SECRET_KEY
  ) {
    const { userId, getToken } = await auth();
    return userId ? await getToken() : null;
  }
  return null;
}
