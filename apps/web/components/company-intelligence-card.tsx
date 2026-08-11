"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge, Card, ErrorState, Skeleton } from "@/components/ui";
import { titleCase } from "@/lib/utils";

type Intelligence = {
  company_name: string;
  active_job_count: number;
  known_job_count: number;
  work_modes: Record<string, number>;
  seniority_mix: Record<string, number>;
  top_skills: Array<{ name: string; job_mentions: number }>;
  compensation: { observed_minimum: number | null; observed_maximum: number | null; postings_with_compensation: number };
  signals: { visa_sponsorship: string; remote_language_present: boolean; ai_language_present: boolean; leadership_hiring_present: boolean };
  disclaimer: string;
};

async function load(jobId: string): Promise<Intelligence> {
  const response = await fetch(`/api/backend/company-intelligence/jobs/${jobId}`);
  if (!response.ok) throw new Error("Company context is unavailable");
  return response.json() as Promise<Intelligence>;
}

function sponsorshipLabel(value: string) {
  const normalized = value.toUpperCase();
  if (normalized === "YES" || normalized === "PRESENT") return "Sponsorship mentioned";
  if (normalized === "NO" || normalized === "NOT_PRESENT") return "No sponsorship mention";
  return "Sponsorship unclear";
}

export function CompanyIntelligenceCard({ jobId }: { jobId: string }) {
  const query = useQuery({ queryKey: ["company-intelligence", jobId], queryFn: () => load(jobId) });
  if (query.isLoading) return <Skeleton className="detail-section" />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message} retry={() => query.refetch()} />;

  const data = query.data;
  return (
    <Card className="detail-section">
      <div className="section-header">
        <div>
          <p className="eyebrow">Company context</p>
          <h2>What current openings suggest</h2>
          <p>A quick look at patterns across the roles ApplyAI has seen from {data.company_name}.</p>
        </div>
        <Badge tone="info">{data.active_job_count} active {data.active_job_count === 1 ? "role" : "roles"}</Badge>
      </div>

      <div className="dashboard-grid">
        <div><strong>{data.known_job_count}</strong><p className="muted">roles observed</p></div>
        <div><strong>{data.compensation.postings_with_compensation}</strong><p className="muted">roles showing pay</p></div>
        <div><strong>{sponsorshipLabel(data.signals.visa_sponsorship)}</strong><p className="muted">based on listing language</p></div>
      </div>

      {data.top_skills.length ? (
        <div>
          <p className="eyebrow" style={{ marginBottom: 8 }}>Common skills in current openings</p>
          <div className="chips">
            {data.top_skills.slice(0, 10).map((skill) => <Badge key={skill.name}>{skill.name}</Badge>)}
          </div>
        </div>
      ) : null}

      <div className="button-row">
        {Object.entries(data.work_modes).map(([mode, count]) => <Badge tone="info" key={mode}>{titleCase(mode)} · {count}</Badge>)}
        {data.signals.ai_language_present ? <Badge tone="success">AI-related hiring</Badge> : null}
        {data.signals.leadership_hiring_present ? <Badge tone="success">Leadership roles open</Badge> : null}
      </div>

      <p className="muted">These patterns come only from job listings ApplyAI has observed. They may not represent company-wide policy.</p>
    </Card>
  );
}
