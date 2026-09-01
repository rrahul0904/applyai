"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, Compass, Target } from "lucide-react";
import { useState } from "react";

import { Badge, Button, Card, ErrorState, Input, PageHeader, Skeleton } from "@/components/ui";
import { growthApi } from "@/lib/api/growth";

export function CareerNavigationWorkspace() {
  const [draftRole, setDraftRole] = useState("");
  const [targetRole, setTargetRole] = useState<string | undefined>(undefined);
  const navigation = useQuery({
    queryKey: ["career-navigation", targetRole ?? "default"],
    queryFn: ({ signal }) => growthApi.careerNavigation(targetRole, signal),
  });

  if (navigation.isLoading) return <Skeleton className="page-skeleton" />;
  if (navigation.isError || !navigation.data) return <ErrorState message={navigation.error?.message ?? "Career Navigation is unavailable."} retry={() => navigation.refetch()} />;
  const data = navigation.data;
  const market = data.market;

  return <>
    <PageHeader eyebrow="Career Navigation" title="See the next roles your evidence can support." description="ApplyAI compares your verified skills with its current canonical job corpus to explain adjacent roles, skill gaps, and market signals. This is direction—not a prediction of your career." />
    <Card className="detail-section">
      <div className="section-header"><div><h2>Explore a target role</h2><p>Current target: <strong>{data.target_role}</strong></p></div><Target size={22}/></div>
      <div className="button-row"><Input value={draftRole} onChange={(event) => setDraftRole(event.target.value)} placeholder="e.g. Senior Data Engineer" /><Button disabled={!draftRole.trim()} onClick={() => setTargetRole(draftRole.trim())}>Analyze role</Button></div>
      <p className="muted">Sample: {market.sample_size} active non-seed postings · {market.coverage_caveat}</p>
    </Card>

    <div className="dashboard-grid">
      <Card><p className="eyebrow">Current role</p><h2>{data.current_role ?? "Not set"}</h2></Card>
      <Card><p className="eyebrow">Market sample</p><h2>{market.sample_size}</h2><p>active postings</p></Card>
      <Card><p className="eyebrow">Explicit salary sample</p><h2>{market.salary.sample_size}</h2><p>{market.salary.median_explicit_usd_yearly_midpoint ? `$${market.salary.median_explicit_usd_yearly_midpoint.toLocaleString()} median midpoint` : "Not enough explicit salary data"}</p></Card>
    </div>

    <div className="detail-grid">
      <div className="detail-main list-stack">
        <Card className="detail-section"><div className="section-header"><div><h2>Evidence strengths</h2><p>Skills already supported by your saved candidate evidence and present in this role sample.</p></div><Compass size={20}/></div><div className="list-stack">{data.evidence_strengths.length ? data.evidence_strengths.map((item) => <div key={item.skill}><Badge tone="success">Evidenced</Badge> <strong>{item.skill}</strong> · {item.posting_count} sampled postings</div>) : <p className="muted">No direct overlap yet. Add or verify career evidence before treating a skill as yours.</p>}</div></Card>
        <Card className="detail-section"><h2>Skill gaps to investigate</h2><div className="list-stack">{data.skill_gaps.map((item) => <div key={item.skill}><Badge tone="warning">Not evidenced</Badge> <strong>{item.skill}</strong> · seen in {item.posting_count} postings</div>)}</div>{data.preparation.length ? <><h3>Preparation ideas</h3><ul>{data.preparation.map((item) => <li key={item}>{item}</li>)}</ul></> : null}</Card>
        <Card className="detail-section"><h2>Adjacent roles in this sample</h2>{data.adjacent_roles.length ? data.adjacent_roles.map((role) => <article key={role.role} style={{marginBottom:12}}><strong>{role.role}</strong> <Badge>{role.posting_count} postings</Badge><p className="muted">{role.reason}</p></article>) : <p className="muted">The current sample is too narrow to suggest adjacent role titles reliably.</p>}</Card>
      </div>
      <aside className="detail-aside list-stack">
        <Card className="detail-section"><div className="section-header"><h2>Work modes</h2><BarChart3 size={18}/></div>{Object.entries(market.work_modes).map(([name, count]) => <p key={name}>{name}: <strong>{count}</strong></p>)}</Card>
        <Card className="detail-section"><h2>Top locations</h2>{market.locations.map((item) => <p key={item.location}>{item.location}: <strong>{item.count}</strong></p>)}</Card>
        <Card className="detail-section"><h2>Common skills</h2>{market.top_skills.slice(0,8).map((item) => <p key={item.skill}>{item.skill} <ArrowRight size={13} style={{verticalAlign:"middle"}}/> {item.posting_count}</p>)}</Card>
      </aside>
    </div>
  </>;
}
