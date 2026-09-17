"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Badge, Button, Card } from "@/components/ui";
import { prepareApi, type ApplicationKit } from "@/lib/api/prepare-client";

function downloadHref(path: string) {
  return `/api/backend${path}`;
}

function scoreTone(score: number) {
  if (score >= 80) return "success" as const;
  if (score >= 60) return "info" as const;
  return "warning" as const;
}

export function ApplicationKitPanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const kit = useQuery<ApplicationKit | null>({
    queryKey: ["prepare-application-kit", jobId],
    queryFn: async ({ signal }) => {
      try {
        return await prepareApi.applicationKit(jobId, signal);
      } catch (error) {
        if (error instanceof Error && /not generated/i.test(error.message)) return null;
        throw error;
      }
    },
    retry: false,
  });
  const generate = useMutation({
    mutationFn: () => prepareApi.createApplicationKit(jobId),
    onSuccess: async (data) => {
      queryClient.setQueryData(["prepare-application-kit", jobId], data);
      toast.success(data.version > 1 ? "Application kit refreshed" : "Application kit generated");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (kit.isLoading) {
    return <Card className="detail-section"><p className="muted">Loading application materials…</p></Card>;
  }

  if (kit.isError) {
    return <Card className="detail-section"><h2>Application kit</h2><p className="muted">{kit.error.message}</p><Button variant="secondary" onClick={() => kit.refetch()}>Try again</Button></Card>;
  }

  if (!kit.data) {
    return (
      <Card className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Application materials</p>
            <h2>Tailor the resume and cover letter to this job</h2>
            <p>ApplyAI uses only verified profile evidence, keeps missing requirements explicit, and produces clean PDF downloads without watermarks.</p>
          </div>
          <Button onClick={() => generate.mutate()} disabled={generate.isPending}><Sparkles size={16}/>{generate.isPending ? "Generating…" : "Generate application kit"}</Button>
        </div>
        <div className="cx-trust-list" style={{ marginTop: 16 }}>
          <div><ShieldCheck size={16}/><span>No invented skills, metrics, employers, or experience.</span></div>
        </div>
      </Card>
    );
  }

  const data = kit.data;
  const ats = data.content.ats;
  return (
    <Card className="detail-section">
      <div className="section-header">
        <div>
          <p className="eyebrow">Application kit · version {data.version}</p>
          <h2>{data.content.job.company} — {data.content.job.title}</h2>
          <p>Evidence-safe resume and cover letter tailored to the role.</p>
        </div>
        <div className="button-row">
          <Badge tone={scoreTone(ats.score)}>ATS alignment {ats.score}%</Badge>
          <Button size="small" variant="ghost" onClick={() => generate.mutate()} disabled={generate.isPending}><RefreshCw size={14}/>Refresh</Button>
        </div>
      </div>

      <div className="dashboard-grid" style={{ marginTop: 16 }}>
        <div>
          <p className="eyebrow">Verified matches</p>
          <div className="chips">{ats.matched_skills.length ? ats.matched_skills.map((skill) => <Badge key={skill} tone="success">{skill}</Badge>) : <span className="muted">No direct verified matches yet.</span>}</div>
        </div>
        <div>
          <p className="eyebrow">Requirements to address</p>
          <div className="chips">{ats.missing_required_skills.length ? ats.missing_required_skills.map((skill) => <Badge key={skill} tone="warning">{skill}</Badge>) : <Badge tone="success">No required skill gaps</Badge>}</div>
        </div>
      </div>

      <div className="detail-grid" style={{ marginTop: 18 }}>
        <div className="detail-main">
          <div className="result-card">
            <p className="eyebrow">Tailored resume</p>
            <h3>{data.content.resume.headline}</h3>
            <p>{data.content.resume.summary}</p>
            <div className="chips">{data.content.resume.skills.slice(0, 10).map((skill) => <Badge key={skill}>{skill}</Badge>)}</div>
          </div>
          <div className="result-card" style={{ marginTop: 14 }}>
            <p className="eyebrow">Tailored cover letter</p>
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{data.content.cover_letter}</div>
          </div>
        </div>
        <aside className="detail-aside">
          <div className="sticky-actions">
            <p className="eyebrow">Downloads</p>
            <a className="ui-button" href={downloadHref(data.downloads.resume_pdf)}><Download size={16}/>Resume PDF</a>
            <a className="ui-button ui-button-secondary" href={downloadHref(data.downloads.cover_letter_pdf)}><FileText size={16}/>Cover letter PDF</a>
            <p className="muted" style={{ marginTop: 12 }}><ShieldCheck size={14} style={{ verticalAlign: "middle", marginRight: 5 }}/>{ats.policy}</p>
          </div>
        </aside>
      </div>
    </Card>
  );
}
