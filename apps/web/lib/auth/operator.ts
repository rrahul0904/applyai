import "server-only";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getApplyAISession } from "@/lib/auth/session";

export async function requireOperatorEmail(): Promise<string> {
  const session = await getApplyAISession();
  if (!session.authenticated) throw new Error("AUTH_REQUIRED");

  let email = session.email;
  if (session.kind === "clerk") {
    const user = await currentUser();
    email = user?.primaryEmailAddress?.emailAddress ?? null;
  } else {
    // Local/E2E dev auth keeps the web-side allowlist because there is no Clerk JWT.
    const allowed = new Set(
      (process.env.APPLYAI_OPERATOR_EMAILS ?? "")
        .split(",")
        .map((value) => value.trim().toLowerCase())
        .filter(Boolean),
    );
    if (allowed.size && (!email || !allowed.has(email.toLowerCase()))) {
      throw new Error("FORBIDDEN");
    }
  }

  if (!email) throw new Error("AUTH_REQUIRED");
  return email;
}

export async function operatorApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  await requireOperatorEmail();
  const apiUrl = process.env.APPLYAI_API_URL;
  if (!apiUrl) throw new Error("Operator API is not configured");

  const session = await getApplyAISession();
  if (!session.authenticated) throw new Error("AUTH_REQUIRED");

  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("content-type", "application/json");

  if (session.kind === "clerk") {
    const { userId, getToken } = await auth();
    if (!userId) throw new Error("AUTH_REQUIRED");
    const token = await getToken();
    if (!token) throw new Error("SESSION_EXPIRED");
    headers.set("authorization", `Bearer ${token}`);
  } else {
    const token = process.env.INTERNAL_API_TOKEN;
    if (!token) throw new Error("Operator API is not configured for development auth");
    headers.set("x-applyai-internal-token", token);
  }

  const response = await fetch(
    new URL(`/api/v1/internal/${path.replace(/^\//, "")}`, apiUrl),
    {
      ...init,
      headers,
      cache: "no-store",
    },
  );

  if (response.status === 401) throw new Error("AUTH_REQUIRED");
  if (response.status === 403) throw new Error("FORBIDDEN");
  if (!response.ok) throw new Error(`Operator API request failed (${response.status})`);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
