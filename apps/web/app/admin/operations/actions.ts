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
