import Link from "next/link";
import { redirect } from "next/navigation";

import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";

import { recordOperationsCertification, refreshOperationSource } from "./actions";

type Summary = {
  generated_at: string;
  jobs: { total: number; active: number };
  sources: { total: number; enabled: number; healthy: number; failing: number; due: number };
  ingestion: {
    runs_24h: number;
    failed_24h: number;
    fetched_24h: number;
    created_24h: number;
    updated_24h: number;
    closed_24h: number;
    pending_source_tasks: number;
  };
  certification: {
    records: number;
    latest: Certification | null;
  };
};

type Source = {
  id: string;
  source_name: string;
  source_type: string;
  source_identity: string;
  enabled: boolean;
  crawl_allowed: boolean;
  health_status: string;
  last_job_count: number;
  last_change_count: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  next_run_at: string;
  updated_at: string;
};

type IngestionRun = {
  id: string;
  source_id: string | null;
  source_type: string | null;
  connector: string;
  source_company: string;
  status: string;
  fetched: number;
  created: number;
  updated: number;
  closed: number;
  failed: number;
  duration_ms: number | null;
  error_category: string | null;
  started_at: string;
  completed_at: string | null;
};

type Certification = {
  id: string;
  certification_type: string;
  status: "PASS" | "FAIL" | "BLOCKED";
  environment: string;
  git_sha: string | null;
  evidence: Record<string, unknown>;
  notes: string | null;
  created_by: string | null;
  created_at: string;
};

type CursorPage<T> = { items: T[]; next_cursor: string | null };

function tone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "PASS" || status === "HEALTHY" || status === "SUCCEEDED") return "success";
  if (status === "FAIL" || status === "FAILING" || status.startsWith("FAILED")) return "danger";
  if (status === "BLOCKED" || status === "RUNNING" || status === "QUEUED") return "warning";
  return "neutral";
}

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export default async function OperationsPage() {
  try {
    await requireOperatorEmail();
  } catch {
    redirect("/dashboard");
  }

  const [summary, sources, ingestion, certifications] = await Promise.all([
    operatorApi<Summary>("operations/summary"),
    operatorApi<CursorPage<Source>>("operations/sources?limit=25"),
    operatorApi<CursorPage<IngestionRun>>("operations/ingestion?limit=25"),
    operatorApi<CursorPage<Certification>>("operations/certifications?limit=25"),
  ]);

  return (
    <main className="app-main">
      <PageHeader
        eyebrow="Release control"
        title="ApplyAI Operations Control"
        description="Repository-backed operational truth for jobs, sources, ingestion and release certification. Refresh actions are durable and certification decisions are persisted."
        action={<Link className="button button-secondary" href="/admin">Back to admin</Link>}
      />

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <h2>Jobs</h2>
            <p>Canonical inventory only. Synthetic scale evidence is not counted as production job supply.</p>
          </div>
          <Badge tone="success">{summary.jobs.active.toLocaleString()} active</Badge>
        </div>
        <div className="dashboard-grid">
          <div><p className="eyebrow">Active jobs</p><h2>{summary.jobs.active.toLocaleString()}</h2></div>
          <div><p className="eyebrow">Total canonical jobs</p><h2>{summary.jobs.total.toLocaleString()}</h2></div>
        </div>
      </Card>

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <h2>Sources</h2>
            <p>Policy-aware source health. “Refresh now” creates a durable SOURCE_INGEST outbox task instead of doing network work inside the browser request.</p>
          </div>
          <Badge tone={summary.sources.failing ? "warning" : "success"}>
            {summary.sources.healthy} healthy · {summary.sources.failing} failing
          </Badge>
        </div>
        <div className="dashboard-grid">
          <div><p className="eyebrow">Registered</p><h2>{summary.sources.total}</h2></div>
          <div><p className="eyebrow">Enabled</p><h2>{summary.sources.enabled}</h2></div>
          <div><p className="eyebrow">Due</p><h2>{summary.sources.due}</h2></div>
        </div>
        <div className="list-stack">
          {sources.items.map((source) => (
            <div className="note" key={source.id}>
              <div className="section-header">
                <div>
                  <strong>{source.source_name}</strong>
                  <p>{source.source_type} · {source.source_identity}</p>
                </div>
                <Badge tone={tone(source.health_status)}>{source.health_status}</Badge>
              </div>
              <p>
                {source.last_job_count} jobs · {source.last_change_count} changes · last success {formatDate(source.last_success_at)}
              </p>
              <form action={refreshOperationSource}>
                <input type="hidden" name="source_id" value={source.id} />
                <Button
                  size="small"
                  type="submit"
                  disabled={!source.enabled || !source.crawl_allowed}
                >
                  Refresh now
                </Button>
              </form>
            </div>
          ))}
          {sources.items.length === 0 && <p>No job sources are registered yet.</p>}
        </div>
        {sources.next_cursor && <p className="eyebrow">More sources available through the cursor API.</p>}
      </Card>

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <h2>Ingestion</h2>
            <p>Recent source runs and queue pressure from the durable ingestion pipeline.</p>
          </div>
          <Badge tone={summary.ingestion.failed_24h ? "warning" : "success"}>
            {summary.ingestion.runs_24h} runs / 24h
          </Badge>
        </div>
        <div className="dashboard-grid">
          <div><p className="eyebrow">Fetched</p><h2>{summary.ingestion.fetched_24h.toLocaleString()}</h2></div>
          <div><p className="eyebrow">Created</p><h2>{summary.ingestion.created_24h.toLocaleString()}</h2></div>
          <div><p className="eyebrow">Updated</p><h2>{summary.ingestion.updated_24h.toLocaleString()}</h2></div>
          <div><p className="eyebrow">Pending source tasks</p><h2>{summary.ingestion.pending_source_tasks}</h2></div>
        </div>
        <div className="list-stack">
          {ingestion.items.map((run) => (
            <div className="note" key={run.id}>
              <div className="section-header">
                <div>
                  <strong>{run.source_company}</strong>
                  <p>{run.connector} · {formatDate(run.started_at)}</p>
                </div>
                <Badge tone={tone(run.status)}>{run.status}</Badge>
              </div>
              <p>
                {run.fetched} fetched · {run.created} created · {run.updated} updated · {run.closed} closed
                {run.error_category ? ` · ${run.error_category}` : ""}
              </p>
            </div>
          ))}
          {ingestion.items.length === 0 && <p>No ingestion runs have been recorded yet.</p>}
        </div>
        {ingestion.next_cursor && <p className="eyebrow">More ingestion runs available through the cursor API.</p>}
      </Card>

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <h2>Certification</h2>
            <p>Persisted release evidence. A PASS is an operator assertion and does not replace automated CI/provider acceptance.</p>
          </div>
          <Badge tone={summary.certification.latest ? tone(summary.certification.latest.status) : "neutral"}>
            {summary.certification.latest?.status ?? "NOT RECORDED"}
          </Badge>
        </div>
        <form action={recordOperationsCertification} className="note">
          <label htmlFor="certification-notes"><strong>Release note</strong></label>
          <textarea
            id="certification-notes"
            name="notes"
            rows={3}
            placeholder="What was verified, what failed, or why the release is blocked?"
          />
          <div className="button-row">
            <Button type="submit" name="status" value="PASS">Record PASS</Button>
            <Button type="submit" name="status" value="BLOCKED" variant="secondary">Record BLOCKED</Button>
            <Button type="submit" name="status" value="FAIL" variant="secondary">Record FAIL</Button>
          </div>
        </form>
        <div className="list-stack">
          {certifications.items.map((item) => (
            <div className="note" key={item.id}>
              <div className="section-header">
                <div>
                  <strong>{item.certification_type}</strong>
                  <p>{item.environment} · {formatDate(item.created_at)}</p>
                </div>
                <Badge tone={tone(item.status)}>{item.status}</Badge>
              </div>
              <p>{item.git_sha ? `Git ${item.git_sha.slice(0, 12)}` : "Git SHA not recorded"} · {item.created_by ?? "operator"}</p>
              {item.notes && <p>{item.notes}</p>}
            </div>
          ))}
          {certifications.items.length === 0 && <p>No certification decisions have been recorded.</p>}
        </div>
        {certifications.next_cursor && <p className="eyebrow">More certification records available through the cursor API.</p>}
      </Card>

      <p className="eyebrow">Generated {formatDate(summary.generated_at)} UTC</p>
    </main>
  );
}
