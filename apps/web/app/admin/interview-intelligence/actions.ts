"use server";

import { revalidatePath } from "next/cache";
import { operatorApi } from "@/lib/auth/operator";

export async function moderateInterviewReport(formData: FormData) {
  const reportId = String(formData.get("report_id") ?? "");
  const decision = String(formData.get("decision") ?? "");
  if (!reportId || !["APPROVED", "REJECTED"].includes(decision)) throw new Error("Invalid moderation action");
  await operatorApi(`interview-intelligence/reports/${reportId}/moderate`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
  revalidatePath("/admin/interview-intelligence");
}

export async function linkInterviewEvidence(formData: FormData) {
  const reportId = String(formData.get("report_id") ?? "");
  const questionId = String(formData.get("question_id") ?? "");
  const confidence = Number(formData.get("confidence") ?? 80);
  if (!reportId || !questionId) throw new Error("Report and question are required");
  await operatorApi(`interview-intelligence/evidence/reports/${reportId}/link`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId, confidence }),
  });
  revalidatePath("/admin/interview-intelligence");
}
