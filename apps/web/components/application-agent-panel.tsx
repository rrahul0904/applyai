"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Bot, CheckCircle2, ExternalLink, FileText, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { api, type AIJobRun } from "@/lib/api/client";
import {
  ApplicationAgentError,
  applicationAgentApi,
  type ApplicationAgentField,
  type ApplicationExecution,
} from "@/lib/api/application-agent";
import { Badge, Button, Card, Field, Input, Textarea } from "@/components/ui";
import { titleCase } from "@/lib/utils";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForRun(run: AIJobRun): Promise<AIJobRun> {
  let current = run;
  for (let attempt = 0; attempt < 45; attempt += 1) {
    if (current.status === "COMPLETED") return current;
    if (current.status === "FAILED") throw new Error(current.error_code || "AI preparation failed");
    await sleep(1000);
    current = await api.careerV2.run(current.id);
  }
  throw new Error("The AI package is still processing. Try again in a moment.");
}

function toneForState(state: string): "neutral" | "success" | "warning" | "info" | "danger" {
  if (state === "CONFIRMED") return "success";
  if (["FAILED"].includes(state)) return "danger";
  if (["NEEDS_INPUT", "REVIEW_REQUIRED", "HUMAN_ACTION_REQUIRED", "SUBMITTED"].includes(state)) return "warning";
  if (["READY_FOR_APPROVAL", "READY_FOR_EXECUTION", "BROWSER_QUEUED", "BROWSER_RUNNING"].includes(state)) return "info";
  return "neutral";
}

function valueText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function FieldEditor({
  execution,
  item,
  onSaved,
}: {
  execution: ApplicationExecution;
  item: ApplicationAgentField;
  onSaved: (data: ApplicationExecution) => void;
}) {
  const [value, setValue] = useState(valueText(item.value));
  const [remember, setRemember] = useState(item.sensitive);
  const mutation = useMutation({
    mutationFn: () => applicationAgentApi.reviewField(execution.id, item.field_id, value, remember),
    onSuccess: (data) => {
      onSaved(data);
      toast.success(remember ? "Answer verified and saved for future applications" : "Answer verified");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "We couldn't save this answer."),
  });
  const needsAction = item.status === "NEEDS_INPUT" || item.requires_review || !item.candidate_verified;
  if (!needsAction) {
    return (
      <div className="note" style={{ display: "grid", gap: 6 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <strong>{item.label}</strong>
          <Badge tone={item.sensitive ? "warning" : "success"}>{item.sensitive ? "Pre-approved" : "Verified"}</Badge>
        </div>
        <p>{valueText(item.value) || "—"}</p>
        <span className="muted">{titleCase(item.source_kind)} · {Math.round(item.confidence * 100)}% confidence</span>
      </div>
    );
  }
  const id = `application-field-${item.field_id}`;
  const input = item.field_type === "TEXTAREA" || value.length > 180
    ? <Textarea id={id} value={value} onChange={(event) => setValue(event.target.value)} rows={5} />
    : <Input id={id} value={value} onChange={(event) => setValue(event.target.value)} />;
  return (
    <div className="note" style={{ display: "grid", gap: 10 }}>
      <Field
        label={item.label}
        htmlFor={id}
        hint={`${item.required ? "Required" : "Optional"} · ${item.sensitive ? "Sensitive answer — explicit confirmation required" : `${Math.round(item.confidence * 100)}% confidence`}`}
      >
        {input}
      </Field>
      <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
        <span>Remember this verified answer for similar future applications</span>
      </label>
      <div className="button-row">
        <Button size="small" onClick={() => mutation.mutate()} disabled={!value.trim() || mutation.isPending}>
          <ShieldCheck size={15} />Verify answer
        </Button>
      </div>
    </div>
  );
}

export function ApplicationAgentPanel({ applicationId, jobId }: { applicationId: string; jobId: string }) {
  const queryClient = useQueryClient();
  const execution = useQuery({
    queryKey: ["application-agent", applicationId],
    queryFn: async ({ signal }) => {
      try {
        return await applicationAgentApi.latest(applicationId, signal);
      } catch (error) {
        if (error instanceof ApplicationAgentError && error.status === 404) return null;
        throw error;
      }
    },
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state && ["BROWSER_QUEUED", "BROWSER_RUNNING", "SUBMITTED"].includes(state) ? 2500 : false;
    },
  });

  const setExecution = (data: ApplicationExecution) => {
    queryClient.setQueryData(["application-agent", applicationId], data);
  };

  const prepare = useMutation({
    mutationFn: async () => {
      await waitForRun(await api.careerV2.start(jobId, "resume-tailoring"));
      await waitForRun(await api.careerV2.start(jobId, "application-copilot"));
      return applicationAgentApi.prepare(applicationId, "SMART");
    },
    onSuccess: (data) => {
      setExecution(data);
      toast.success("Application package prepared");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "We couldn't prepare this application."),
  });

  const approve = useMutation({
    mutationFn: (id: string) => applicationAgentApi.approve(id),
    onSuccess: (data) => {
      setExecution(data);
      toast.success("Application package approved");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Review is still required."),
  });

  const execute = useMutation({
    mutationFn: (id: string) => applicationAgentApi.execute(id),
    onSuccess: (data) => {
      setExecution(data);
      toast.success("Application sent to the browser agent");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "We couldn't start browser execution."),
  });

  if (execution.isLoading) {
    return <Card className="detail-section"><p className="muted">Loading application agent…</p></Card>;
  }
  if (execution.isError) {
    return <Card className="detail-section"><p className="field-error">{execution.error.message}</p></Card>;
  }

  const item = execution.data;
  if (!item) {
    return (
      <Card className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">AI application agent</p>
            <h2>Prepare this application end to end</h2>
            <p>Generate an evidence-locked resume, cover letter and answers, then review anything sensitive before browser execution.</p>
          </div>
          <Bot size={28} aria-hidden="true" />
        </div>
        <div className="note" style={{ marginTop: 14 }}>
          <strong>Truth-first application policy</strong>
          <p>ApplyAI can reframe verified experience for the role, but it will not invent qualifications, metrics, credentials or work history.</p>
        </div>
        <div className="button-row" style={{ marginTop: 16 }}>
          <Button onClick={() => prepare.mutate()} disabled={prepare.isPending}>
            <Sparkles size={17} />{prepare.isPending ? "Preparing application…" : "Analyze & prepare application"}
          </Button>
        </div>
      </Card>
    );
  }

  const actionableFields = item.fields.filter((field) => field.status === "NEEDS_INPUT" || field.requires_review || !field.candidate_verified);
  const readyFields = item.fields.filter((field) => !actionableFields.includes(field));
  const canApprove = item.missing_fields.length === 0 && item.review_items.length === 0 && item.state === "READY_FOR_APPROVAL";
  const humanAction = item.browser_handoff?.human_action as Record<string, unknown> | undefined;
  const cover = item.documents?.cover_letter;
  const resume = item.documents?.resume;

  return (
    <Card className="detail-section">
      <div className="section-header">
        <div>
          <p className="eyebrow">AI application agent</p>
          <h2>Application execution</h2>
          <p>{item.ats_provider} · attempt {item.attempt_number}</p>
        </div>
        <Badge tone={toneForState(item.state)}>{titleCase(item.state)}</Badge>
      </div>

      {item.state === "CONFIRMED" ? (
        <div className="note" style={{ marginTop: 14, display: "grid", gap: 8 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}><CheckCircle2 size={19} /><strong>Application confirmed</strong></div>
          <p>ApplyAI detected employer-side submission confirmation and updated the application to Applied.</p>
          {item.confirmation_url ? <a href={item.confirmation_url} target="_blank" rel="noreferrer">Open confirmation <ExternalLink size={14} /></a> : null}
        </div>
      ) : null}

      {item.state === "HUMAN_ACTION_REQUIRED" ? (
        <div className="note" style={{ marginTop: 14, display: "grid", gap: 8 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}><AlertTriangle size={19} /><strong>Human action required</strong></div>
          <p>{String(humanAction?.message || "The browser agent reached a step that must be completed manually.")}</p>
          {typeof humanAction?.url === "string" ? <a href={humanAction.url} target="_blank" rel="noreferrer">Open employer application <ExternalLink size={14} /></a> : null}
        </div>
      ) : null}

      <div style={{ display: "grid", gap: 14, marginTop: 18 }}>
        <div>
          <h3>Documents</h3>
          <div className="list-stack" style={{ marginTop: 8 }}>
            <div className="note">
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}><FileText size={17} /><strong>Tailored resume</strong></div>
              <p>{resume?.artifact_id ? `Prepared · ${String(resume.status || "review required")}` : "Not available"}</p>
              <Link href={`/jobs/${jobId}`}>Review resume evidence and tailoring</Link>
            </div>
            <details className="note">
              <summary><strong>Cover letter</strong></summary>
              <p style={{ whiteSpace: "pre-wrap", marginTop: 10 }}>{String(cover?.body || "Cover letter not available")}</p>
            </details>
          </div>
        </div>

        {actionableFields.length ? (
          <div>
            <h3>Needs your review</h3>
            <p className="muted">Unknown, lower-confidence and sensitive answers never pass silently.</p>
            <div className="list-stack" style={{ marginTop: 8 }}>
              {actionableFields.map((field) => <FieldEditor key={field.field_id} execution={item} item={field} onSaved={setExecution} />)}
            </div>
          </div>
        ) : null}

        {readyFields.length ? (
          <details>
            <summary><strong>{readyFields.length} verified fields ready</strong></summary>
            <div className="list-stack" style={{ marginTop: 8 }}>
              {readyFields.map((field) => <FieldEditor key={field.field_id} execution={item} item={field} onSaved={setExecution} />)}
            </div>
          </details>
        ) : null}
      </div>

      <div className="button-row" style={{ marginTop: 18 }}>
        {canApprove ? <Button onClick={() => approve.mutate(item.id)} disabled={approve.isPending}><ShieldCheck size={17} />Approve application package</Button> : null}
        {item.state === "READY_FOR_EXECUTION" ? <Button onClick={() => execute.mutate(item.id)} disabled={execute.isPending}><Bot size={17} />Apply for me</Button> : null}
        {["NEEDS_INPUT", "REVIEW_REQUIRED"].includes(item.state) ? <Badge tone="warning">{item.missing_fields.length} missing · {item.review_items.length} to review</Badge> : null}
        {["BROWSER_QUEUED", "BROWSER_RUNNING"].includes(item.state) ? <Badge tone="info">Browser agent running</Badge> : null}
        {item.target_url ? <a className="ui-button ui-button-ghost ui-button-small" href={item.target_url} target="_blank" rel="noreferrer">Open employer site <ExternalLink size={15} /></a> : null}
      </div>
    </Card>
  );
}
