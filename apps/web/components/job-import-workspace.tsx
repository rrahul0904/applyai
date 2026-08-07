"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, Field, Input, PageHeader } from "@/components/ui";

async function backend<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, { ...init, headers: { "content-type": "application/json", ...init.headers } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.error?.message ?? "Request failed");
  return response.json() as Promise<T>;
}

type ImportResult = { id: string; status: string; input_url: string; detected_provider: string | null; canonical_url: string | null; apply_url: string | null; job_id: string | null; error_category: string | null };

export function JobImportWorkspace() {
  const params = useSearchParams();
  const [url, setUrl] = useState(() => params.get("url") ?? "");
  const [importId, setImportId] = useState<string | null>(null);
  const start = useMutation({ mutationFn: () => backend<ImportResult>("/jobs/import-url", { method: "POST", body: JSON.stringify({ url }) }), onSuccess: (result) => setImportId(result.id) });
  const status = useQuery({ queryKey: ["job-import", importId], queryFn: () => backend<ImportResult>(`/jobs/import-url/${importId}`), enabled: Boolean(importId), refetchInterval: (query) => { const state = (query.state.data as ImportResult | undefined)?.status; return state && !["COMPLETED", "FAILED", "REJECTED"].includes(state) ? 1500 : false; } });
  const result = status.data ?? start.data;
  return <><PageHeader eyebrow="Browser extension handoff" title="Import a job" description="Bring a public employer job URL into ApplyAI's safe discovery pipeline, then match, tailor and track it like any other role." />
    <Card className="detail-section"><form className="form-stack" onSubmit={(event) => { event.preventDefault(); if (url.startsWith("http")) start.mutate(); }}><Field label="Public job URL" htmlFor="import-url"><Input id="import-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://company.com/careers/job..." /></Field><Button type="submit" disabled={!url || start.isPending}><ExternalLink size={16}/>Import job</Button></form></Card>
    {result ? <Card className="detail-section"><div className="section-header"><div><h2>Import status</h2><p>{result.detected_provider ?? "Provider detection in progress"}</p></div><Badge tone={result.status === "COMPLETED" ? "success" : result.status === "FAILED" ? "danger" : "info"}>{result.status}</Badge></div>{result.job_id ? <Link className="ui-button ui-button-primary" href={`/jobs/${result.job_id}`}>Open imported job</Link> : <p className="muted">ApplyAI is validating robots policy, redirects, structured job data and canonical identity before the role enters your workspace.</p>}</Card> : null}
  </>;
}
