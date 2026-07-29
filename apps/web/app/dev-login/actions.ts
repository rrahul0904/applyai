"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { DEV_USER_COOKIE, devAuthEnabled } from "@/lib/auth/session";

export async function devSignIn(formData: FormData) {
  if (!devAuthEnabled()) throw new Error("Development authentication is disabled");
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    redirect("/dev-login?error=invalid-email");
  }
  (await cookies()).set(DEV_USER_COOKIE, email, {
    httpOnly: true,
    sameSite: "strict",
    secure: false,
    path: "/",
    maxAge: 60 * 60 * 12,
  });
  redirect("/onboarding");
}

export async function devSignOut() {
  if (devAuthEnabled()) {
    (await cookies()).delete(DEV_USER_COOKIE);
  }
  redirect("/");
}
