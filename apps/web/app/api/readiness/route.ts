import { NextResponse } from "next/server";

function keyMode(value: string | undefined, livePrefix: string, testPrefix: string) {
  if (!value) return "missing" as const;
  if (value.startsWith(livePrefix)) return "live" as const;
  if (value.startsWith(testPrefix)) return "test" as const;
  return "unknown" as const;
}

export async function GET() {
  const publishableMode = keyMode(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
    "pk_live_",
    "pk_test_",
  );
  const secretMode = keyMode(process.env.CLERK_SECRET_KEY, "sk_live_", "sk_test_");
  const apiConfigured = Boolean(process.env.APPLYAI_API_URL);
  const devAuthEnabled = process.env.DEV_AUTH_ENABLED === "true";
  const operatorConfigured = Boolean(
    process.env.APPLYAI_OPERATOR_EMAILS && process.env.INTERNAL_API_TOKEN,
  );

  const productionReady =
    apiConfigured &&
    publishableMode === "live" &&
    secretMode === "live" &&
    !devAuthEnabled;

  return NextResponse.json(
    {
      service: "applyai-web",
      environment: process.env.VERCEL_ENV ?? process.env.APP_ENV ?? "unknown",
      runtime_ready:
        apiConfigured &&
        publishableMode !== "missing" &&
        secretMode !== "missing" &&
        !devAuthEnabled,
      production_ready: productionReady,
      checks: {
        api_configured: apiConfigured,
        clerk_publishable_key_mode: publishableMode,
        clerk_secret_key_mode: secretMode,
        dev_auth_enabled: devAuthEnabled,
        operator_configured: operatorConfigured,
      },
    },
    {
      status: productionReady || process.env.VERCEL_ENV !== "production" ? 200 : 503,
      headers: { "cache-control": "no-store" },
    },
  );
}
