import { createHash } from "node:crypto";
import { NextResponse } from "next/server";

function keyMode(value: string | undefined, livePrefix: string, testPrefix: string) {
  if (!value) return "missing" as const;
  if (value.startsWith(livePrefix)) return "live" as const;
  if (value.startsWith(testPrefix)) return "test" as const;
  return "unknown" as const;
}

function publishableKeyInstanceFingerprint(value: string | undefined) {
  if (!value || !/^pk_(test|live)_/.test(value)) return "";
  try {
    const encoded = value.replace(/^pk_(test|live)_/, "");
    const decoded = Buffer.from(encoded, "base64").toString("utf8").replace(/\$$/, "");
    const normalized = decoded.includes("://") ? decoded : `https://${decoded}`;
    const hostname = new URL(normalized).hostname.trim().toLowerCase();
    return hostname
      ? createHash("sha256").update(hostname).digest("hex").slice(0, 16)
      : "";
  } catch {
    return "";
  }
}

async function backendReadiness(apiUrl: string | undefined) {
  if (!apiUrl) {
    return { reachable: false, operatorConfigured: false, clerkFingerprint: "" };
  }
  try {
    const response = await fetch(new URL("/ready", apiUrl), {
      cache: "no-store",
      signal: AbortSignal.timeout(3_000),
    });
    if (!response.ok) {
      return { reachable: false, operatorConfigured: false, clerkFingerprint: "" };
    }
    const payload = (await response.json().catch(() => null)) as
      | {
          operator_auth_configured?: boolean;
          clerk_instance_fingerprint?: string;
        }
      | null;
    return {
      reachable: true,
      operatorConfigured: payload?.operator_auth_configured === true,
      clerkFingerprint:
        typeof payload?.clerk_instance_fingerprint === "string"
          ? payload.clerk_instance_fingerprint
          : "",
    };
  } catch {
    return { reachable: false, operatorConfigured: false, clerkFingerprint: "" };
  }
}

export async function GET() {
  const publishableMode = keyMode(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
    "pk_live_",
    "pk_test_",
  );
  const secretMode = keyMode(process.env.CLERK_SECRET_KEY, "sk_live_", "sk_test_");
  const apiConfigured = Boolean(process.env.APPLYAI_API_URL);
  const backend = await backendReadiness(process.env.APPLYAI_API_URL);
  const devAuthEnabled = process.env.DEV_AUTH_ENABLED === "true";
  const webClerkFingerprint = publishableKeyInstanceFingerprint(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
  );
  const clerkInstanceMatch = Boolean(
    webClerkFingerprint &&
      backend.clerkFingerprint &&
      webClerkFingerprint === backend.clerkFingerprint,
  );

  const runtimeReady =
    apiConfigured &&
    backend.reachable &&
    publishableMode !== "missing" &&
    secretMode !== "missing" &&
    clerkInstanceMatch &&
    !devAuthEnabled;

  const productionReady =
    runtimeReady &&
    publishableMode === "live" &&
    secretMode === "live" &&
    backend.operatorConfigured;

  return NextResponse.json(
    {
      service: "applyai-web",
      environment: process.env.VERCEL_ENV ?? process.env.APP_ENV ?? "unknown",
      runtime_ready: runtimeReady,
      production_ready: productionReady,
      checks: {
        api_configured: apiConfigured,
        api_reachable: backend.reachable,
        clerk_publishable_key_mode: publishableMode,
        clerk_secret_key_mode: secretMode,
        clerk_instance_match: clerkInstanceMatch,
        dev_auth_enabled: devAuthEnabled,
        operator_configured: backend.operatorConfigured,
        operator_auth_location: "api",
      },
    },
    {
      status: productionReady || process.env.VERCEL_ENV !== "production" ? 200 : 503,
      headers: { "cache-control": "no-store" },
    },
  );
}
