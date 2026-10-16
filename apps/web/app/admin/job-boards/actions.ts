"use server";

import { revalidatePath } from "next/cache";
import { operatorApi } from "@/lib/auth/operator";

function value(formData: FormData, key: string) {
  return String(formData.get(key) ?? "").trim();
}

export async function createJobBoard(formData: FormData) {
  const slug = value(formData, "slug");
  const name = value(formData, "name");
  const description = value(formData, "description");
  if (!slug || !name) throw new Error("Board name and slug are required");
  await operatorApi("job-boards", {
    method: "POST",
    body: JSON.stringify({ slug, name, description: description || null, visibility: "PUBLIC", metadata_json: {} }),
  });
  revalidatePath("/admin/job-boards");
  revalidatePath("/job-boards");
}

export async function addBoardSource(formData: FormData) {
  const boardId = value(formData, "board_id");
  const sourceRegistryId = value(formData, "source_registry_id");
  if (!boardId || !sourceRegistryId) throw new Error("Board and source IDs are required");
  await operatorApi(`job-boards/${encodeURIComponent(boardId)}/sources`, {
    method: "POST",
    body: JSON.stringify({ source_registry_id: sourceRegistryId, priority: 50 }),
  });
  revalidatePath("/admin/job-boards");
  revalidatePath("/job-boards");
}

export async function reviewBoardClaim(formData: FormData) {
  const claimId = value(formData, "claim_id");
  const decision = value(formData, "decision").toUpperCase();
  if (!claimId || !["APPROVED", "REJECTED"].includes(decision)) throw new Error("Invalid claim review");
  await operatorApi(`job-boards/claims/${encodeURIComponent(claimId)}/review`, {
    method: "POST",
    body: JSON.stringify({ status: decision }),
  });
  revalidatePath("/admin/job-boards");
}

export async function executePublication(formData: FormData) {
  const publicationId = value(formData, "publication_id");
  if (!publicationId) throw new Error("Publication ID is required");
  await operatorApi(`job-boards/publications/${encodeURIComponent(publicationId)}/publish`, { method: "POST" });
  revalidatePath("/admin/job-boards");
}
