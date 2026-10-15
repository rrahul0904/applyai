type BackendReadiness = {
  reachable: boolean;
  contractValid: boolean;
  upstreamStatus: number | null;
  failureClass: "API_NOT_CONFIGURED" | "UPSTREAM_NON_2XX" | "INVALID_READINESS_PAYLOAD" | "UPSTREAM_UNREACHABLE" | null;
  databaseReachable: boolean;
  databaseMigrationsCurrent: boolean;
  operatorConfigured: boolean;
  operatorAuthLocation: string;
  storageConfigured: boolean;
  storageReachable: boolean;
  authConfigured: boolean;
  authInstanceMatch: boolean;
  taskQueueConfigured: boolean;
  backgroundWorkerConfigured: boolean;
  backgroundWorkerHealthy: boolean;
  deploymentSha: string;
  authProvider: string;
  clerkFingerprint: string;
  supabaseFingerprint: string;
};

function isBackendReadinessPayload(value: unknown): value is {
  status: "ready";
  database_reachable: boolean;
  database_migrations_current: boolean;
  storage_reachable: boolean;
  auth_configured: boolean;
  auth_instance_match: boolean;
  operator_auth_configured: boolean;
  operator_auth_location: string;
  storage_configured: boolean;
  task_queue_configured: boolean;
  background_worker_configured: boolean;
  background_worker_healthy: boolean;
  deployment_sha: string;
  auth_provider: "clerk" | "supabase";
  clerk_instance_fingerprint: string;
  supabase_project_fingerprint: string;
} {
  if (!value || typeof value !== "object") return false;
  const payload = value as Record<string, unknown>;
  return (
    payload.status === "ready" &&
    typeof payload.database_reachable === "boolean" &&
    typeof payload.database_migrations_current === "boolean" &&
    typeof payload.storage_reachable === "boolean" &&
    typeof payload.auth_configured === "boolean" &&
    typeof payload.auth_instance_match === "boolean" &&
    typeof payload.operator_auth_configured === "boolean" &&
    typeof payload.operator_auth_location === "string" &&
    typeof payload.storage_configured === "boolean" &&
    typeof payload.task_queue_configured === "boolean" &&
    typeof payload.background_worker_configured === "boolean" &&
    typeof payload.background_worker_healthy === "boolean" &&
    typeof payload.deployment_sha === "string" &&
    (payload.auth_provider === "clerk" || payload.auth_provider === "supabase") &&
    typeof payload.clerk_instance_fingerprint === "string" &&
    typeof payload.supabase_project_fingerprint === "string"
  );
}

export function authInstanceMatches(expectedFingerprint: string, actualFingerprint: string): boolean {
  return Boolean(expectedFingerprint && actualFingerprint && expectedFingerprint === actualFingerprint);
}

export async function backendReadiness(apiUrl: string | undefined): Promise<BackendReadiness> {
  const empty = {
    reachable: false,
    contractValid: false,
    upstreamStatus: null,
    failureClass: apiUrl
      ? "UPSTREAM_UNREACHABLE" as const
      : "API_NOT_CONFIGURED" as const,
    databaseReachable: false,
    databaseMigrationsCurrent: false,
    operatorConfigured: false,
    operatorAuthLocation: "",
    storageConfigured: false,
    storageReachable: false,
    authConfigured: false,
    authInstanceMatch: false,
    taskQueueConfigured: false,
    backgroundWorkerConfigured: false,
    backgroundWorkerHealthy: false,
    deploymentSha: "",
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
    if (!response.ok) {
      return { ...empty, upstreamStatus: response.status, failureClass: "UPSTREAM_NON_2XX" };
    }
    const payload: unknown = await response.json().catch(() => null);
    if (!isBackendReadinessPayload(payload)) {
      return { ...empty, upstreamStatus: response.status, failureClass: "INVALID_READINESS_PAYLOAD" };
    }
    return {
      reachable: true,
      contractValid: true,
      upstreamStatus: response.status,
      failureClass: null,
      databaseReachable: payload.database_reachable,
      databaseMigrationsCurrent: payload.database_migrations_current,
      operatorConfigured: payload.operator_auth_configured,
      operatorAuthLocation: payload.operator_auth_location,
      storageConfigured: payload.storage_configured,
      storageReachable: payload.storage_reachable,
      authConfigured: payload.auth_configured,
      authInstanceMatch: payload.auth_instance_match,
      taskQueueConfigured: payload.task_queue_configured,
      backgroundWorkerConfigured: payload.background_worker_configured,
      backgroundWorkerHealthy: payload.background_worker_healthy,
      deploymentSha: payload.deployment_sha,
      authProvider: payload.auth_provider,
      clerkFingerprint: payload.clerk_instance_fingerprint,
      supabaseFingerprint: payload.supabase_project_fingerprint,
    };
  } catch {
    return empty;
  }
}

