"use server";

import { revalidatePath } from "next/cache";
import { operatorApi } from "@/lib/auth/operator";

const PATH = "/admin/reverse-engineering";

function lines(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export async function createReverseEngineeringTopic(formData: FormData) {
  const title = String(formData.get("title") ?? "").trim();
  if (!title) return;
  const manualFit = String(formData.get("applyai_fit") ?? "").trim();
  await operatorApi("reverse-engineering/topics", {
    method: "POST",
    body: JSON.stringify({
      title,
      source_url: String(formData.get("source_url") ?? "").trim() || null,
      source_type: String(formData.get("source_type") ?? "").trim() || "PUBLIC_RESEARCH",
      summary: String(formData.get("summary") ?? "").trim(),
      ...(manualFit ? { applyai_fit: manualFit } : {}),
      qualifying_capabilities: lines(formData.get("qualifying_capabilities")),
      excluded_capabilities: lines(formData.get("excluded_capabilities")),
      evidence_urls: lines(formData.get("evidence_urls")),
      implementation_target: String(formData.get("implementation_target") ?? "").trim() || null,
      status: String(formData.get("status") ?? "RESEARCHED"),
    }),
  });
  revalidatePath(PATH);
}

export async function reclassifyReverseEngineeringTopic(formData: FormData) {
  const id = String(formData.get("topic_id") ?? "");
  if (!id) return;
  await operatorApi(`reverse-engineering/topics/${id}/reclassify`, { method: "POST" });
  revalidatePath(PATH);
}

export async function updateReverseEngineeringTopicStatus(formData: FormData) {
  const id = String(formData.get("topic_id") ?? "");
  const status = String(formData.get("status") ?? "");
  if (!id || !status) return;
  await operatorApi(`reverse-engineering/topics/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  revalidatePath(PATH);
}
