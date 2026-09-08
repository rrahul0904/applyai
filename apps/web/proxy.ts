import { clerkMiddleware } from "@clerk/nextjs/server";
import type { NextFetchEvent, NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { refreshSupabaseSessionProxy } from "@/lib/auth/supabase-proxy";
import { supabaseConfigured } from "@/lib/auth/supabase-http";

const clerkAuthenticationProxy = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
  ? clerkMiddleware()
  : null;

export default async function authenticationProxy(
  request: NextRequest,
  event: NextFetchEvent,
) {
  if (supabaseConfigured()) {
    return refreshSupabaseSessionProxy(request);
  }
  if (clerkAuthenticationProxy) {
    return clerkAuthenticationProxy(request, event);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
  ],
};
