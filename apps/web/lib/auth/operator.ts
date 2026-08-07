import "server-only";
import { currentUser } from "@clerk/nextjs/server";
import { getApplyAISession } from "@/lib/auth/session";

export async function requireOperatorEmail(): Promise<string> {
  const session = await getApplyAISession();
  if (!session.authenticated) throw new Error("AUTH_REQUIRED");
  let email = session.email;
  if (session.kind === "clerk") {
    const user = await currentUser();
    email = user?.primaryEmailAddress?.emailAddress ?? null;
  }
  const allowed = new Set((process.env.APPLYAI_OPERATOR_EMAILS ?? "").split(",").map((value) => value.trim().toLowerCase()).filter(Boolean));
  if (!email || !allowed.has(email.toLowerCase())) throw new Error("FORBIDDEN");
  return email;
}

export async function operatorApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  await requireOperatorEmail();
  const apiUrl = process.env.APPLYAI_API_URL;
  const token = process.env.INTERNAL_API_TOKEN;
  if (!apiUrl || !token) throw new Error("Operator API is not configured");
  const response = await fetch(new URL(`/api/v1/internal/${path.replace(/^\//, "")}`, apiUrl), {
    ...init,
    headers: { "x-applyai-internal-token": token, "content-type": "application/json", ...init.headers },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Operator API request failed (${response.status})`);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
