"use client";

import { useQuery } from "@tanstack/react-query";
import { Printer, ShieldCheck } from "lucide-react";

import { Badge, Button, Card, ErrorState } from "@/components/ui";
import type { RecruiterLensSnapshot } from "@/lib/api/recruiter-lens";
import { titleCase } from "@/lib/utils";

async function loadReport(token: string, signal?: AbortSignal): Promise<RecruiterLensSnapshot & { privacy: Record<string, boolean> }> {
  const response = await fetch(`/api/public-backend/recruiter-lens/public/reports/${encodeURIComponent(token)}`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(response.status === 404 ? "This report is unavailable or has been revoked." : "We could not load this report.");
  }
  return response.json();
}

export function PublicRecruiterLensReport({ token }: { token: string }) {
  const report = useQuery({
    queryKey: ["public-recruiter-lens-report", token],
    queryFn: ({ signal }) => loadReport(token, signal),
  });

  if (report.isLoading) {
    return <main style={{ maxWidth: 920, margin: "48px auto", padding: 24 }}><p>Loading candidate-controlled report…</p></main>;
  }
  if (report.isError || !report.data) {
    return <main style={{ maxWidth: 920, margin: "48px auto", padding: 24 }}><ErrorState message={report.error?.message ?? "Report unavailable"} retry={() => report.refetch()} /></main>;
  }

  const item = report.data;
  return (
    <main style={{ maxWidth: 920, margin: "48px auto", padding: 24, display: "grid", gap: 20 }}>
      <header>
        <p className="eyebrow">Candidate-controlled self-assessment</p>
        <h1>Recruiter Lens report</h1>
        <p>{item.report.job_title ?? "Role assessment"}</p>
        <Button variant="ghost" onClick={() => window.print()}><Printer size={16} />Print report</Button>
      </header>

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 20, flexWrap: "wrap" }}>
          <div><p className="eyebrow">Readiness</p><h2>{item.score}% · Tier {item.tier}</h2></div>
          <Badge>{titleCase(item.mode)}</Badge>
        </div>
        <p>{item.disclaimer}</p>
      </Card>

      <Card>
        <h2>Evidence criteria</h2>
        <div style={{ display: "grid", gap: 12 }}>
          {item.criteria.map((criterion) => (
            <article key={criterion.id} style={{ borderTop: "1px solid currentColor", paddingTop: 12 }}>
              <strong>{criterion.label}</strong> <Badge>{titleCase(criterion.status)}</Badge>
              <p>{criterion.evidence?.snippet ?? "No explicit verified evidence was found for this criterion."}</p>
            </article>
          ))}
        </div>
      </Card>

      {item.concerns.length ? <Card><h2>Preparation concerns</h2><ul>{item.concerns.map((concern) => <li key={`${concern.criterion_id}-${concern.message}`}>{concern.message}</li>)}</ul></Card> : null}
      {item.interview_questions.length ? <Card><h2>Questions to prepare for</h2><ul>{item.interview_questions.map((question) => <li key={`${question.criterion_id}-${question.question}`}>{question.question}</li>)}</ul></Card> : null}

      <Card>
        <p style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
          <ShieldCheck size={18} />
          <span>This link was explicitly created by the candidate. It is not an employer decision, hiring probability, named-viewer tracker, or company-identity inference.</span>
        </p>
      </Card>
    </main>
  );
}
