import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import {
  exchangeSupabasePkceCode,
  SUPABASE_OAUTH_STATE_COOKIE,
  SUPABASE_PKCE_VERIFIER_COOKIE,
} from "@/lib/auth/supabase-http";
import { persistSupabaseSession } from "@/lib/auth/supabase-session";

export async function GET(request: NextRequest) {
  const authCode = request.nextUrl.searchParams.get("code");
  const returnedState = request.nextUrl.searchParams.get("state");
  const store = await cookies();
  const verifier = store.get(SUPABASE_PKCE_VERIFIER_COOKIE)?.value;
  const expectedState = store.get(SUPABASE_OAUTH_STATE_COOKIE)?.value;

  store.delete(SUPABASE_PKCE_VERIFIER_COOKIE);
  store.delete(SUPABASE_OAUTH_STATE_COOKIE);

  if (!authCode || !returnedState || !expectedState || returnedState !== expectedState || !verifier) {
    return NextResponse.redirect(new URL("/sign-in?error=oauth_state", request.url));
  }

  try {
    const session = await exchangeSupabasePkceCode(authCode, verifier);
    await persistSupabaseSession(session);
    return NextResponse.redirect(new URL("/dashboard", request.url));
  } catch {
    return NextResponse.redirect(new URL("/sign-in?error=oauth_exchange", request.url));
  }
}
