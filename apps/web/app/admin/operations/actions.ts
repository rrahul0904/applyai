"use server";

import { revalidatePath } from "next/cache";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";

export async function refreshOperationSource(formData: FormData) {
  const sourceId = String(formData.get("source_id") ?? "");
  if (!sourceId) return;
  await operatorApi(`operations/sources/${sourceId}/refresh`, { method: "POST" });
  revalidatePath("/admin/operations");
}

export async function recordOperationsCertification(formData: FormData) {
  const email = await requireOperatorEmail();
  const requestedStatus = String(formData.get("status") ?? "BLOCKED").toUpperCase();
  const status = ["PASS", "FAIL", "BLOCKED"].includes(requestedStatus)
    ? requestedStatus
    : "BLOCKED";
  const notes = String(formData.get("notes") ?? "").trim() || null;
  await operatorApi("operations/certifications", {
    method: "POST",
    body: JSON.stringify({
      certification_type: "FULL_FUNCTIONAL",
      status,
      environment: process.env.VERCEL_ENV ?? process.env.APP_ENV ?? "operator",
      git_sha: process.env.VERCEL_GIT_COMMIT_SHA ?? null,
      evidence: {
        source: "admin-operations",
        recorded_at: new Date().toISOString(),
      },
      notes,
      created_by: email,
    }),
  });
  revalidatePath("/admin/operations");
}


function dollarsToCents(value: FormDataEntryValue | null) {
  const parsed = Number(String(value ?? "0").trim() || "0");
  if (!Number.isFinite(parsed) || parsed < 0) return 0;
  return Math.round(parsed * 100);
}

export async function recordServiceCost(formData: FormData) {
  await requireOperatorEmail();
  const serviceKey = String(formData.get("service_key") ?? "").trim().toLowerCase();
  const displayName = String(formData.get("display_name") ?? "").trim();
  const provider = String(formData.get("provider") ?? "").trim();
  const category = String(formData.get("category") ?? "").trim();
  const billingPeriod = String(formData.get("billing_period") ?? "").trim();
  if (!serviceKey || !displayName || !provider || !category || !billingPeriod) return;

  await operatorApi("operations/service-costs", {
    method: "POST",
    body: JSON.stringify({
      service_key: serviceKey,
      display_name: displayName,
      provider,
      category,
      environment: String(formData.get("environment") ?? process.env.VERCEL_ENV ?? "production"),
      billing_period: billingPeriod,
      fixed_cost_cents: dollarsToCents(formData.get("fixed_cost_usd")),
      usage_cost_cents: dollarsToCents(formData.get("usage_cost_usd")),
      credits_cents: dollarsToCents(formData.get("credits_usd")),
      currency: "USD",
      source: String(formData.get("source") ?? "operator").trim() || "operator",
      notes: String(formData.get("notes") ?? "").trim() || null,
    }),
  });
  revalidatePath("/admin/operations");
}
