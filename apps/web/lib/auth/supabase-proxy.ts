import { NextRequest, NextResponse } from "next/server";
import {
  accessTokenNeedsRefresh,
  refreshSupabaseToken,
  SUPABASE_ACCESS_COOKIE,
  SUPABASE_REFRESH_COOKIE,
  supabaseConfigured,
} from "./supabase-http";

const REFRESH_COOKIE_SECONDS = 60 * 60 * 24 * 365;

function cookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
  };
}

export async function refreshSupabaseSessionProxy(request: NextRequest) {
  let response = NextResponse.next({ request });
  if (!supabaseConfigured()) return response;

  const accessToken = request.cookies.get(SUPABASE_ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(SUPABASE_REFRESH_COOKIE)?.value;
  if (accessToken && !accessTokenNeedsRefresh(accessToken)) return response;
  if (!refreshToken) return response;

  try {
    const session = await refreshSupabaseToken(refreshToken);
    // Server components and API forwarding run during this request, before the
    // browser receives Set-Cookie. Forward the refreshed tokens to them as well.
    request.cookies.set(SUPABASE_ACCESS_COOKIE, session.access_token);
    request.cookies.set(SUPABASE_REFRESH_COOKIE, session.refresh_token);
    response = NextResponse.next({ request: { headers: request.headers } });
    response.cookies.set(SUPABASE_ACCESS_COOKIE, session.access_token, {
      ...cookieOptions(),
      maxAge: Math.max(60, session.expires_in),
    });
    response.cookies.set(SUPABASE_REFRESH_COOKIE, session.refresh_token, {
      ...cookieOptions(),
      maxAge: REFRESH_COOKIE_SECONDS,
    });
  } catch {
    request.cookies.delete(SUPABASE_ACCESS_COOKIE);
    request.cookies.delete(SUPABASE_REFRESH_COOKIE);
    response = NextResponse.next({ request: { headers: request.headers } });
    response.cookies.delete(SUPABASE_ACCESS_COOKIE);
    response.cookies.delete(SUPABASE_REFRESH_COOKIE);
  }
  return response;
}
