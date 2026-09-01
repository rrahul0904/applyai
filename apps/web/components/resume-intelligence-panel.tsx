"use client";

import { useQuery } from "@tanstack/react-query";
import { FileSearch, ShieldCheck } from "lucide-react";

import { Badge, Card, ErrorState } from "@/components/ui";

async function loadResumeIntelligence(signal?: AbortSignal) {
  const response = await fetch("/api/backend/resume-intelligence", { signal, cache: "no-store" });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { error?: { message?: string } } | null;
    throw new Error(payload?.error?.message ?? "Resume Intelligence is unavailable.");
  }
  return response.json() as Promise<{
    filename: string;
    word_count: number;
    checks: Array<{ id: string; label: string; status: "PASS" | "NEEDS_ATTENTION" | "REVIEW_REQUIRED"; detail: string }>;
    policy: { ats_probability: false; hiring_probability: false };
  }>;
}

function tone(status: string) {
  if (status === "PASS") return "success" as const;
  if (status === "NEEDS_ATTENTION") return "warning" as const;
  return "info" as const;
}

export function ResumeIntelligencePanel() {
  const intelligence = useQuery({ queryKey: ["resume-intelligence"], queryFn: ({ signal }) => loadResumeIntelligence(signal), retry: false });
  if (intelligence.isError) return <Card className="detail-section"><ErrorState message={intelligence.error.message} retry={() => intelligence.refetch()} /></Card>;
  if (intelligence.isLoading || !intelligence.data) return <Card className="detail-section"><p>Checking resume readiness…</p></Card>;
  return <Card className="detail-section">
    <div className="section-header"><div><p className="eyebrow">Resume Intelligence</p><h2>Explainable readiness checks</h2><p>Deterministic checks for parseability, completeness, evidence visibility, generic language and readability.</p></div><FileSearch size={23}/></div>
    <div className="list-stack">{intelligence.data.checks.map((check) => <article key={check.id}><div className="button-row"><strong>{check.label}</strong><Badge tone={tone(check.status)}>{check.status.replaceAll("_", " ")}</Badge></div><p className="muted">{check.detail}</p></article>)}</div>
    <p className="muted"><ShieldCheck size={15} style={{verticalAlign:"text-bottom"}} /> ApplyAI does not expose an opaque ATS score or hiring probability. Candidate review remains the final evidence check.</p>
  </Card>;
}
