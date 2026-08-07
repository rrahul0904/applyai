"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge, Card, ErrorState, Skeleton } from "@/components/ui";

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
  if (!response.ok) throw new Error("Company intelligence is unavailable");
  return response.json() as Promise<Intelligence>;
}

export function CompanyIntelligenceCard({ jobId }: { jobId: string }) {
  const query = useQuery({ queryKey: ["company-intelligence", jobId], queryFn: () => load(jobId) });
  if (query.isLoading) return <Skeleton className="detail-section" />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message} retry={() => query.refetch()} />;
  const data = query.data;
  return <Card className="detail-section">
    <div className="section-header"><div><h2>Company intelligence</h2><p>Evidence from ApplyAI's currently known job postings.</p></div><Badge tone="info">{data.active_job_count} active roles</Badge></div>
    <div className="dashboard-grid"><div><strong>{data.known_job_count}</strong><p className="muted">known roles</p></div><div><strong>{data.compensation.postings_with_compensation}</strong><p className="muted">pay-transparent roles</p></div><div><strong>{data.signals.visa_sponsorship.replaceAll("_", " ")}</strong><p className="muted">sponsorship signal</p></div></div>
    {data.top_skills.length ? <div className="chips">{data.top_skills.slice(0,10).map((skill)=><Badge key={skill.name}>{skill.name} · {skill.job_mentions}</Badge>)}</div> : null}
    <div className="button-row">{Object.entries(data.work_modes).map(([mode,count])=><Badge tone="info" key={mode}>{mode} {count}</Badge>)}{data.signals.ai_language_present ? <Badge tone="success">AI hiring signal</Badge> : null}{data.signals.leadership_hiring_present ? <Badge tone="success">Leadership hiring</Badge> : null}</div>
    <p className="muted">{data.disclaimer}</p>
  </Card>;
}
