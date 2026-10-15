import { NextResponse } from "next/server";
import { authInstanceMatches, backendReadiness } from "./backend-readiness";
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


export async function GET() {
  const apiConfigured = Boolean(process.env.APPLYAI_API_URL);
  const backend = await backendReadiness(process.env.APPLYAI_API_URL);
  const devAuthEnabled = process.env.DEV_AUTH_ENABLED === "true";

  const supabaseUrl = configuredSupabaseUrl();
  const supabasePublishableKey = configuredSupabasePublishableKey();
  const useSupabase = Boolean(supabaseUrl || supabasePublishableKey);
  const webSupabaseFingerprint = supabaseProjectFingerprint(supabaseUrl);
  const supabaseInstanceMatch = authInstanceMatches(
    webSupabaseFingerprint,
    backend.supabaseFingerprint,
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
  const clerkInstanceMatch = authInstanceMatches(
    webClerkFingerprint,
    backend.clerkFingerprint,
  );

  const providerReady = useSupabase
    ? Boolean(
        supabaseUrl &&
          supabasePublishableKey &&
          backend.authProvider === "supabase" &&
          backend.authConfigured &&
          backend.authInstanceMatch &&
          supabaseInstanceMatch,
      )
    : Boolean(
        clerkPublishableMode !== "missing" &&
          clerkSecretMode !== "missing" &&
          backend.authProvider === "clerk" &&
          backend.authConfigured &&
          backend.authInstanceMatch &&
          clerkInstanceMatch,
      );

  const runtimeReady =
    apiConfigured &&
    backend.reachable &&
    backend.databaseReachable &&
    backend.databaseMigrationsCurrent &&
    backend.storageConfigured &&
    backend.storageReachable &&
    backend.taskQueueConfigured &&
    backend.backgroundWorkerConfigured &&
    backend.backgroundWorkerHealthy &&
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
        api_contract_valid: backend.contractValid,
        api_upstream_status: backend.upstreamStatus,
        api_failure_class: backend.failureClass,
        database_reachable: backend.databaseReachable,
        database_migrations_current: backend.databaseMigrationsCurrent,
        storage_configured: backend.storageConfigured,
        storage_reachable: backend.storageReachable,
        auth_configured: backend.authConfigured,
        auth_instance_match: backend.authInstanceMatch,
        task_queue_configured: backend.taskQueueConfigured,
        background_worker_configured: backend.backgroundWorkerConfigured,
        background_worker_healthy: backend.backgroundWorkerHealthy,
        api_deployment_sha: backend.deploymentSha,
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
