import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";

export const DEV_USER_COOKIE = "applyai_dev_user";

export type ApplyAISession =
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
