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

export async function enableAgentDefinition(formData: FormData) {
  const name = String(formData.get("agent_name") ?? "");
  const version = String(formData.get("agent_version") ?? "");
  if (!name || !version) return;
  await operatorApi(`agents/definitions/${name}/${version}/enabled`, {
    method: "POST",
    body: JSON.stringify({ enabled: true, reason: "Operator enabled from admin" }),
  });
  revalidatePath("/admin");
}

export async function disableAgentDefinition(formData: FormData) {
  const name = String(formData.get("agent_name") ?? "");
  const version = String(formData.get("agent_version") ?? "");
  if (!name || !version) return;
  await operatorApi(`agents/definitions/${name}/${version}/enabled`, {
    method: "POST",
    body: JSON.stringify({ enabled: false, reason: "Operator paused from admin" }),
  });
  revalidatePath("/admin");
}

export async function retryAgentRun(formData: FormData) {
  const id = String(formData.get("run_id") ?? "");
  if (!id) return;
  await operatorApi(`agents/runs/${id}/retry`, { method: "POST" });
  revalidatePath("/admin");
}

export async function cancelAgentRun(formData: FormData) {
  const id = String(formData.get("run_id") ?? "");
  if (!id) return;
  await operatorApi(`agents/runs/${id}/cancel`, { method: "POST" });
  revalidatePath("/admin");
}
