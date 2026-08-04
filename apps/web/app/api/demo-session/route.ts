import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { DEV_USER_COOKIE, devAuthEnabled } from "@/lib/auth/session";

const DEMO_EMAIL = "applyai.demo@example.test";

export async function POST() {
  if (!devAuthEnabled()) {
    return NextResponse.json(
      {
        error: {
          code: "DEMO_SESSION_DISABLED",
          message: "The account-free demo session is available only in local and test environments.",
        },
      },
      { status: 404 },
    );
  }

  (await cookies()).set(DEV_USER_COOKIE, DEMO_EMAIL, {
    httpOnly: true,
    sameSite: "strict",
    secure: false,
    path: "/",
    maxAge: 60 * 60 * 12,
  });

  return NextResponse.json({ authenticated: true, email: DEMO_EMAIL });
}
