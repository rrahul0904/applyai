"use server";

import { revalidatePath } from "next/cache";
import { operatorApi } from "@/lib/auth/operator";

export async function verifyOrganization(formData: FormData) {
  const id = String(formData.get("organization_id") ?? "");
  if (!id) return;
  await operatorApi(`platform/organizations/${id}/verify`, { method: "POST" });
  revalidatePath("/admin");
}

export async function suspendOrganization(formData: FormData) {
  const id = String(formData.get("organization_id") ?? "");
  if (!id) return;
  await operatorApi(`platform/organizations/${id}/suspend`, { method: "POST" });
  revalidatePath("/admin");
}

export async function dispatchEngagement() {
  await operatorApi("platform/dispatch-engagement", { method: "POST" });
  revalidatePath("/admin");
}

export async function enableJobSource(formData: FormData) {
  const id = String(formData.get("source_id") ?? "");
  if (!id) return;
  await operatorApi(`job-supply/sources/${id}/enable`, { method: "POST" });
  revalidatePath("/admin");
}

export async function disableJobSource(formData: FormData) {
  const id = String(formData.get("source_id") ?? "");
  if (!id) return;
  await operatorApi(`job-supply/sources/${id}/disable`, { method: "POST" });
  revalidatePath("/admin");
}

export async function refreshJobSource(formData: FormData) {
  const id = String(formData.get("source_id") ?? "");
  if (!id) return;
  await operatorApi(`job-supply/sources/${id}/refresh`, { method: "POST" });
  revalidatePath("/admin");
}

export async function discoverOrganizationJobs(formData: FormData) {
  const id = String(formData.get("organization_profile_id") ?? "");
  if (!id) return;
  await operatorApi(`job-supply/organizations/${id}/discover`, { method: "POST" });
  revalidatePath("/admin");
}
