import "server-only";
import { cookies } from "next/headers";
import {
  getSupabaseUser,
  SUPABASE_ACCESS_COOKIE,
  SUPABASE_REFRESH_COOKIE,
  type SupabaseAuthUser,
  type SupabaseTokenResponse,
} from "./supabase-http";

const REFRESH_COOKIE_SECONDS = 60 * 60 * 24 * 365;

function cookieSecurity() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
  };
}

export async function persistSupabaseSession(session: SupabaseTokenResponse) {
  const store = await cookies();
  store.set(SUPABASE_ACCESS_COOKIE, session.access_token, {
    ...cookieSecurity(),
    maxAge: Math.max(60, session.expires_in),
  });
  store.set(SUPABASE_REFRESH_COOKIE, session.refresh_token, {
    ...cookieSecurity(),
    maxAge: REFRESH_COOKIE_SECONDS,
  });
}

export async function clearSupabaseSession() {
  const store = await cookies();
  store.delete(SUPABASE_ACCESS_COOKIE);
  store.delete(SUPABASE_REFRESH_COOKIE);
}

export async function getValidatedSupabaseSession(): Promise<{
  user: SupabaseAuthUser;
  accessToken: string;
} | null> {
  const store = await cookies();
  const accessToken = store.get(SUPABASE_ACCESS_COOKIE)?.value;
  if (!accessToken) return null;
  const user = await getSupabaseUser(accessToken);
  return user ? { user, accessToken } : null;
}
