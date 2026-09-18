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


export async function recordServiceCost(formData: FormData) {
  await requireOperatorEmail();
  const provider = String(formData.get("provider") ?? "").trim();
  const service = String(formData.get("service") ?? "").trim();
  const category = String(formData.get("category") ?? "OTHER").toUpperCase();
  const costType = String(formData.get("cost_type") ?? "INVOICE").toUpperCase();
  const amountUsd = Number(formData.get("amount_usd") ?? NaN);
  const periodStart = String(formData.get("period_start") ?? "").trim();
  const periodEnd = String(formData.get("period_end") ?? "").trim();
  if (!provider || !service || !Number.isFinite(amountUsd) || amountUsd < 0 || !periodStart || !periodEnd) {
    return;
  }
  await operatorApi("operations/costs", {
    method: "POST",
    body: JSON.stringify({
      provider,
      service,
      category,
      cost_type: costType,
      amount_usd: amountUsd,
      period_start: new Date(`${periodStart}T00:00:00Z`).toISOString(),
      period_end: new Date(`${periodEnd}T23:59:59Z`).toISOString(),
      source_ref: String(formData.get("source_ref") ?? "").trim() || null,
      notes: String(formData.get("notes") ?? "").trim() || null,
    }),
  });
  revalidatePath("/admin/operations");
}
