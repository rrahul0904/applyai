import { NextResponse } from "next/server";
import { clerkPublishableKeyInstanceFingerprint } from "@/lib/auth/clerk-instance";
import { supabaseProjectFingerprint } from "@/lib/auth/supabase-instance";
import {
  configuredSupabasePublishableKey,
  configuredSupabaseUrl,
} from "@/lib/auth/supabase-http";

function keyMode(value: string | undefined, livePrefix: string, testPrefix: string) {
  if (!value) return "missing" as const;
  if (value.startsWith(livePrefix)) return "live" as const;
  if (value.startsWith(testPrefix)) return "test" as const;
  return "unknown" as const;
}

async function backendReadiness(apiUrl: string | undefined) {
  const empty = {
    reachable: false,
    databaseReachable: false,
    operatorConfigured: false,
    operatorAuthLocation: "",
    storageConfigured: false,
    backgroundWorkerConfigured: false,
    authProvider: "",
    clerkFingerprint: "",
    supabaseFingerprint: "",
  };
  if (!apiUrl) return empty;
  try {
    const response = await fetch(new URL("/ready", apiUrl), {
      cache: "no-store",
      signal: AbortSignal.timeout(3_000),
    });
    if (!response.ok) return empty;
    const payload = (await response.json().catch(() => null)) as
      | {
          database_reachable?: boolean;
          operator_auth_configured?: boolean;
          operator_auth_location?: string;
          storage_configured?: boolean;
          background_worker_configured?: boolean;
          auth_provider?: string;
          clerk_instance_fingerprint?: string;
          supabase_project_fingerprint?: string;
        }
      | null;
    return {
      reachable: true,
      databaseReachable: payload?.database_reachable === true,
      operatorConfigured: payload?.operator_auth_configured === true,
      operatorAuthLocation:
        typeof payload?.operator_auth_location === "string"
          ? payload.operator_auth_location
          : "",
      storageConfigured: payload?.storage_configured === true,
      backgroundWorkerConfigured:
        payload?.background_worker_configured === true,
      authProvider:
        typeof payload?.auth_provider === "string" ? payload.auth_provider : "",
      clerkFingerprint:
        typeof payload?.clerk_instance_fingerprint === "string"
          ? payload.clerk_instance_fingerprint
          : "",
      supabaseFingerprint:
        typeof payload?.supabase_project_fingerprint === "string"
          ? payload.supabase_project_fingerprint
          : "",
    };
  } catch {
    return empty;
  }
}

export async function GET() {
  const apiConfigured = Boolean(process.env.APPLYAI_API_URL);
  const backend = await backendReadiness(process.env.APPLYAI_API_URL);
  const devAuthEnabled = process.env.DEV_AUTH_ENABLED === "true";

  const supabaseUrl = configuredSupabaseUrl();
  const supabasePublishableKey = configuredSupabasePublishableKey();
  const useSupabase = Boolean(supabaseUrl || supabasePublishableKey);
  const webSupabaseFingerprint = supabaseProjectFingerprint(supabaseUrl);
  const supabaseInstanceMatch = Boolean(
    webSupabaseFingerprint &&
      backend.supabaseFingerprint &&
      webSupabaseFingerprint === backend.supabaseFingerprint,
  );

  const clerkPublishableMode = keyMode(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
    "pk_live_",
    "pk_test_",
  );
  const clerkSecretMode = keyMode(
    process.env.CLERK_SECRET_KEY,
    "sk_live_",
    "sk_test_",
  );
  const webClerkFingerprint = clerkPublishableKeyInstanceFingerprint(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
  );
  const clerkInstanceMatch = Boolean(
    webClerkFingerprint &&
      backend.clerkFingerprint &&
      webClerkFingerprint === backend.clerkFingerprint,
  );

  const providerReady = useSupabase
    ? Boolean(
        supabaseUrl &&
          supabasePublishableKey &&
          backend.authProvider === "supabase" &&
          backend.backgroundWorkerConfigured &&
          supabaseInstanceMatch,
      )
    : Boolean(
        clerkPublishableMode !== "missing" &&
          clerkSecretMode !== "missing" &&
          backend.authProvider === "clerk" &&
          clerkInstanceMatch,
      );

  const runtimeReady =
    apiConfigured &&
    backend.reachable &&
    backend.databaseReachable &&
    backend.storageConfigured &&
    providerReady &&
    !devAuthEnabled;

  const productionReady =
    runtimeReady &&
    backend.operatorConfigured &&
    (useSupabase
      ? backend.operatorAuthLocation === "database"
      : clerkPublishableMode === "live" && clerkSecretMode === "live");

  return NextResponse.json(
    {
      service: "applyai-web",
      environment: process.env.VERCEL_ENV ?? process.env.APP_ENV ?? "unknown",
      runtime_ready: runtimeReady,
      production_ready: productionReady,
      checks: {
        api_configured: apiConfigured,
        api_reachable: backend.reachable,
        database_reachable: backend.databaseReachable,
        storage_configured: backend.storageConfigured,
        background_worker_configured: backend.backgroundWorkerConfigured,
        auth_provider: backend.authProvider,
        supabase_auth_configured: Boolean(
          supabaseUrl && supabasePublishableKey,
        ),
        supabase_instance_match: supabaseInstanceMatch,
        clerk_publishable_key_mode: clerkPublishableMode,
        clerk_secret_key_mode: clerkSecretMode,
        clerk_instance_match: clerkInstanceMatch,
        dev_auth_enabled: devAuthEnabled,
        operator_configured: backend.operatorConfigured,
        operator_auth_location: backend.operatorAuthLocation,
      },
    },
    {
      status:
        productionReady || process.env.VERCEL_ENV !== "production" ? 200 : 503,
      headers: { "cache-control": "no-store" },
    },
  );
}
