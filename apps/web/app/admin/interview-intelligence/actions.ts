"use server";

import { revalidatePath } from "next/cache";
import { operatorApi } from "@/lib/auth/operator";

const PATH = "/admin/interview-intelligence";

export async function moderateInterviewReport(formData: FormData) {
  const reportId = String(formData.get("report_id") ?? "");
  const decision = String(formData.get("decision") ?? "");
  if (!reportId || !decision) return;
  await operatorApi(`interview-intelligence/reports/${reportId}/moderate`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
  revalidatePath(PATH);
}

export async function linkInterviewEvidence(formData: FormData) {
  const reportId = String(formData.get("report_id") ?? "");
  const questionId = String(formData.get("question_id") ?? "");
  if (!reportId || !questionId) return;
  await operatorApi(`interview-intelligence/reports/${reportId}/evidence`, {
    method: "POST",
    body: JSON.stringify({
      question_id: questionId,
      confidence: Number(formData.get("confidence") ?? 75),
      evidence_notes: String(formData.get("evidence_notes") ?? "").trim() || null,
    }),
  });
  revalidatePath(PATH);
}

export async function unlinkInterviewEvidence(formData: FormData) {
  const evidenceId = String(formData.get("evidence_id") ?? "");
  if (!evidenceId) return;
  await operatorApi(`interview-intelligence/evidence/${evidenceId}`, { method: "DELETE" });
  revalidatePath(PATH);
}

export async function createInterviewQuestion(formData: FormData) {
  const title = String(formData.get("title") ?? "").trim();
  const prompt = String(formData.get("prompt") ?? "").trim();
  const summary = String(formData.get("summary") ?? "").trim();
  if (!title || !prompt || !summary) return;
  const lines = (name: string) => String(formData.get(name) ?? "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  await operatorApi("interview-intelligence/questions", {
    method: "POST",
    body: JSON.stringify({
      title,
      prompt,
      summary,
      track: String(formData.get("track") ?? "BEHAVIORAL"),
      difficulty: String(formData.get("difficulty") ?? "MEDIUM"),
      companies: lines("companies"),
      stages: lines("stages"),
      skills: lines("skills"),
      patterns: lines("patterns"),
      hints: lines("hints"),
      follow_ups: lines("follow_ups"),
      solution_outline: lines("solution_outline"),
      frequency_score: Number(formData.get("frequency_score") ?? 0),
      published: formData.get("published") === "on",
    }),
  });
  revalidatePath(PATH);
}
