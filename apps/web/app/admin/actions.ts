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
