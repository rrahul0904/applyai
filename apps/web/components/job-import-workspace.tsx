"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { api } from "@/lib/api/client";

async function backend<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, { ...init, headers: { "content-type": "application/json", ...init.headers } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.error?.message ?? "Request failed");
  return response.json() as Promise<T>;
}

type ImportResult = {
  id: string;
  status: string;
  input_url: string;
  detected_provider: string | null;
  canonical_url: string | null;
  apply_url: string | null;
  job_id: string | null;
  error_category: string | null;
};

export function JobImportWorkspace() {
  const router = useRouter();
  const params = useSearchParams();
  const [url, setUrl] = useState(() => params.get("url") ?? "");
  const [importId, setImportId] = useState<string | null>(null);

  const start = useMutation({
    mutationFn: () => backend<ImportResult>("/jobs/import-url", { method: "POST", body: JSON.stringify({ url }) }),
    onSuccess: (result) => setImportId(result.id),
    onError: (error) => toast.error(error instanceof Error ? error.message : "We couldn't import that job URL."),
  });
  const status = useQuery({
    queryKey: ["job-import", importId],
    queryFn: () => backend<ImportResult>(`/jobs/import-url/${importId}`),
    enabled: Boolean(importId),
    refetchInterval: (query) => {
      const state = (query.state.data as ImportResult | undefined)?.status;
      return state && !["COMPLETED", "FAILED", "REJECTED"].includes(state) ? 1500 : false;
    },
  });
  const result = status.data ?? start.data;

  const apply = useMutation({
    mutationFn: async (jobId: string) => api.applications.create(jobId),
    onSuccess: (application) => {
      toast.success("Job added to your AI application workspace");
      router.push(`/applications/${application.id}`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "We couldn't create the application workspace."),
  });

  return <>
    <PageHeader
      eyebrow="AI job application"
      title="Paste a job link"
      description="Bring a public employer job URL into ApplyAI, validate the role, then tailor your application and apply from one governed workflow."
    />
    <Card className="detail-section">
      <form className="form-stack" onSubmit={(event) => { event.preventDefault(); if (url.startsWith("http")) start.mutate(); }}>
        <Field label="Public job URL" htmlFor="import-url">
          <Input id="import-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://company.com/careers/job..." />
        </Field>
        <Button type="submit" disabled={!url.startsWith("http") || start.isPending}>
          <ExternalLink size={16}/>{start.isPending ? "Analyzing job…" : "Analyze job link"}
        </Button>
      </form>
    </Card>
    {result ? <Card className="detail-section">
      <div className="section-header">
        <div>
          <h2>Job analysis</h2>
          <p>{result.detected_provider ?? "Provider detection in progress"}</p>
        </div>
        <Badge tone={result.status === "COMPLETED" ? "success" : result.status === "FAILED" || result.status === "REJECTED" ? "danger" : "info"}>{result.status}</Badge>
      </div>
      {result.job_id ? <>
        <p className="muted" style={{ marginBottom: 14 }}>The job is normalized and ready for fit analysis, resume tailoring, cover-letter generation, answer review and browser application.</p>
        <div className="button-row">
          <Button onClick={() => apply.mutate(result.job_id!)} disabled={apply.isPending}>
            <Sparkles size={16}/>{apply.isPending ? "Opening application…" : "Continue to AI application"}
          </Button>
          <Link className="ui-button ui-button-secondary ui-button-small" href={`/jobs/${result.job_id}`}>Review job first</Link>
        </div>
      </> : result.status === "FAILED" || result.status === "REJECTED" ? (
        <p className="field-error">ApplyAI could not safely import this URL{result.error_category ? ` (${result.error_category})` : ""}.</p>
      ) : (
        <p className="muted">ApplyAI is validating access policy, redirects, structured job data and canonical identity before the role enters your workspace.</p>
      )}
    </Card> : null}
  </>;
}