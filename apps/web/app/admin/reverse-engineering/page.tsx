import Link from "next/link";
import { redirect } from "next/navigation";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";
import {
  createReverseEngineeringTopic,
  reclassifyReverseEngineeringTopic,
  updateReverseEngineeringTopicStatus,
} from "./actions";

type FitName =
  | "CORE"
  | "PREPARE"
  | "INTELLIGENCE"
  | "INFRASTRUCTURE"
  | "INTEGRATION"
  | "NOT_APPLYAI";

type TaxonomyItem = {
  fit: FitName;
  label: string;
  meaning: string;
  examples: string[];
  default_scope: "FULL" | "PARTIAL" | "NONE";
  destination: string;
};

type Taxonomy = {
  classifier_version: string;
  candidate_journey: string[];
  classifications: TaxonomyItem[];
  summary_contract: string[];
};

type RegistrySummary = {
  total: number;
  by_fit: Record<string, number>;
  by_status: Record<string, number>;
  classifier_version: string;
};

type Topic = {
  id: string;
  title: string;
  source_url: string | null;
  source_type: string;
  summary: string;
  applyai_fit: FitName;
  fit_scope: "FULL" | "PARTIAL" | "NONE";
  destination: string;
  rationale: string;
  classifier_version: string;
  classification_source: "AUTO" | "MANUAL";
  candidate_journey_stages: string[];
  qualifying_capabilities: string[];
  excluded_capabilities: string[];
  evidence_urls: string[];
  status: string;
  implementation_target: string | null;
  created_at: string | null;
  updated_at: string | null;
};

type EvaluationReceipt = {
  id: string;
  subject_type: string;
  subject_name: string;
  subject_version: string;
  content_digest: string;
  dataset_version: string;
  verdict: "PASS" | "NEUTRAL" | "FAIL";
  release_gate: "PASS" | "BLOCK";
  execution_status: "complete" | "partial";
  expected_rows: number;
  scored_rows: number;
  wins: number;
  losses: number;
  ties: number;
  net_lift: number;
  sign_p: number;
  trigger_precision: number | null;
  trigger_recall: number | null;
  baseline_cost_usd: number | null;
  candidate_cost_usd: number | null;
  cost_delta_usd: number | null;
  baseline_duration_ms: number | null;
  candidate_duration_ms: number | null;
  duration_delta_ms: number | null;
  receipt_digest: string;
  gate_reasons: string[];
  provenance: Record<string, unknown>;
  created_at: string | null;
};

const statuses = ["RESEARCHED", "PLANNED", "IMPLEMENTING", "INTEGRATED", "REJECTED"] as const;

function fitTone(fit: FitName): "success" | "warning" | "danger" | "neutral" {
  if (fit === "CORE" || fit === "PREPARE") return "success";
  if (fit === "INTELLIGENCE" || fit === "INFRASTRUCTURE" || fit === "INTEGRATION") return "warning";
  if (fit === "NOT_APPLYAI") return "danger";
  return "neutral";
}

function pretty(value: string): string {
  return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function fitLabel(fit: FitName): string {
  return fit === "NOT_APPLYAI" ? "NOT APPLYAI" : `APPLYAI — ${fit}`;
}

export default async function ReverseEngineeringPage() {
  try {
    await requireOperatorEmail();
  } catch {
    redirect("/dashboard");
  }

  const [taxonomy, summary, topics, receipts] = await Promise.all([
    operatorApi<Taxonomy>("reverse-engineering/taxonomy"),
    operatorApi<RegistrySummary>("reverse-engineering/summary"),
    operatorApi<Topic[]>("reverse-engineering/topics?limit=100"),
    operatorApi<EvaluationReceipt[]>("ai-release-evaluation/receipts?limit=10"),
  ]);

  return (
    <main className="app-main">
      <PageHeader
        eyebrow="Operator-only · Product intelligence"
        title="Reverse Engineering Intake"
        description="Classify every researched capability against the ApplyAI candidate journey, preserve the clean-room boundary, and turn only qualifying behavior into governed implementation work."
        action={<Link href="/admin">Back to operations</Link>}
      />

      <div className="dashboard-grid">
        <Card>
          <p className="eyebrow">Research topics</p>
          <h2>{summary.total}</h2>
          <p>Classifier {summary.classifier_version}</p>
        </Card>
        <Card>
          <p className="eyebrow">Candidate-facing</p>
          <h2>{(summary.by_fit.CORE ?? 0) + (summary.by_fit.PREPARE ?? 0) + (summary.by_fit.INTELLIGENCE ?? 0)}</h2>
          <p>Core + Prepare + Intelligence</p>
        </Card>
        <Card>
          <p className="eyebrow">Platform / integration</p>
          <h2>{(summary.by_fit.INFRASTRUCTURE ?? 0) + (summary.by_fit.INTEGRATION ?? 0)}</h2>
          <p>Reusable platform capability</p>
        </Card>
        <Card>
          <p className="eyebrow">Kept separate</p>
          <h2>{summary.by_fit.NOT_APPLYAI ?? 0}</h2>
          <p>Explicitly outside ApplyAI</p>
        </Card>
      </div>

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <h2>Register reverse-engineering research</h2>
            <p>
              Auto-classification is deterministic and versioned. Choose a fit only when a human override is intentional;
              the registry records whether the decision came from the classifier or an operator.
            </p>
          </div>
          <Badge>{taxonomy.classifier_version}</Badge>
        </div>
        <form action={createReverseEngineeringTopic} className="list-stack">
          <label>
            <strong>Topic / product</strong>
            <input name="title" required maxLength={240} placeholder="e.g. Terum Skills evaluation" />
          </label>
          <label>
            <strong>Source URL</strong>
            <input name="source_url" type="url" placeholder="https://…" />
          </label>
          <label>
            <strong>Source type</strong>
            <select name="source_type" defaultValue="PUBLIC_RESEARCH">
              <option value="PUBLIC_RESEARCH">Public research</option>
              <option value="REDDIT">Reddit</option>
              <option value="GITHUB">GitHub</option>
              <option value="REDDIT_GITHUB">Reddit + GitHub</option>
              <option value="WEBSITE">Website</option>
            </select>
          </label>
          <label>
            <strong>Reverse-engineering summary</strong>
            <textarea
              name="summary"
              rows={5}
              placeholder="Observed behavior, workflows, architecture clues, and user value. Do not paste proprietary source code or hidden implementation details."
            />
          </label>
          <label>
            <strong>ApplyAI Fit</strong>
            <select name="applyai_fit" defaultValue="">
              <option value="">Auto-classify</option>
              {taxonomy.classifications.map((item) => (
                <option key={item.fit} value={item.fit}>{item.label}</option>
              ))}
            </select>
          </label>
          <label>
            <strong>Capabilities to absorb into ApplyAI</strong>
            <textarea name="qualifying_capabilities" rows={4} placeholder="One capability per line" />
          </label>
          <label>
            <strong>Capabilities to keep separate</strong>
            <textarea name="excluded_capabilities" rows={4} placeholder="One capability per line" />
          </label>
          <label>
            <strong>Evidence URLs</strong>
            <textarea name="evidence_urls" rows={3} placeholder="One public evidence URL per line" />
          </label>
          <label>
            <strong>Implementation target</strong>
            <input name="implementation_target" placeholder="e.g. ApplyAI agent evaluation gates" />
          </label>
          <label>
            <strong>Status</strong>
            <select name="status" defaultValue="RESEARCHED">
              {statuses.map((status) => <option key={status} value={status}>{pretty(status)}</option>)}
            </select>
          </label>
          <div><Button type="submit">Register research</Button></div>
        </form>
      </Card>

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <h2>ApplyAI Fit taxonomy</h2>
            <p>The destination is a product boundary, not a quality score.</p>
          </div>
          <Badge>{taxonomy.classifications.length} classes</Badge>
        </div>
        <div className="list-stack">
          {taxonomy.classifications.map((item) => (
            <div className="note" key={item.fit}>
              <div className="section-header">
                <div>
                  <strong>{item.label}</strong>
                  <p>{item.meaning}</p>
                </div>
                <Badge tone={fitTone(item.fit)}>{item.default_scope}</Badge>
              </div>
              <p><strong>Destination:</strong> {item.destination}</p>
              <p>{item.examples.join(" · ")}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <h2>AI release evaluation receipts</h2>
            <p>
              Immutable, content-bound baseline/candidate evidence for agents, skills, prompts, and workflows.
              Partial runs and measured regressions fail closed at the release gate.
            </p>
          </div>
          <Badge>{receipts.length} recent</Badge>
        </div>
        <div className="list-stack">
          {receipts.map((receipt) => (
            <div className="note" key={receipt.id}>
              <div className="section-header">
                <div>
                  <strong>{receipt.subject_name} {receipt.subject_version}</strong>
                  <p>{receipt.subject_type} · dataset {receipt.dataset_version} · {receipt.scored_rows}/{receipt.expected_rows} scored</p>
                </div>
                <div>
                  <Badge tone={receipt.release_gate === "PASS" ? "success" : "danger"}>{receipt.release_gate}</Badge>
                  <p>{receipt.verdict} · {receipt.execution_status}</p>
                </div>
              </div>
              <p>
                <strong>Lift:</strong> {(receipt.net_lift * 100).toFixed(1)}% ·
                {" "}<strong>W/L/T:</strong> {receipt.wins}/{receipt.losses}/{receipt.ties} ·
                {" "}<strong>sign p:</strong> {receipt.sign_p.toFixed(3)}
              </p>
              <p>
                <strong>Triggers:</strong> precision {receipt.trigger_precision == null ? "n/a" : `${(receipt.trigger_precision * 100).toFixed(1)}%`}
                {" · "}recall {receipt.trigger_recall == null ? "n/a" : `${(receipt.trigger_recall * 100).toFixed(1)}%`}
                {" · "}<strong>Cost delta:</strong> {receipt.cost_delta_usd == null ? "n/a" : `$${receipt.cost_delta_usd.toFixed(4)}`}
                {" · "}<strong>Latency delta:</strong> {receipt.duration_delta_ms == null ? "n/a" : `${receipt.duration_delta_ms.toFixed(0)}ms`}
              </p>
              {receipt.gate_reasons.length > 0 && <p><strong>Gate reasons:</strong> {receipt.gate_reasons.join(" · ")}</p>}
              <p><small>Artifact {receipt.content_digest.slice(0, 22)}… · receipt {receipt.receipt_digest.slice(0, 22)}…</small></p>
            </div>
          ))}
          {!receipts.length && <p>No AI release evaluation receipts have been recorded yet.</p>}
        </div>
      </Card>

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <h2>Reverse-engineering registry</h2>
            <p>
              ApplyAI Fit appears first on every record. Human overrides remain visible and can always be reset to the
              current deterministic classifier.
            </p>
          </div>
          <Badge>{topics.length} shown</Badge>
        </div>

        <div className="list-stack">
          {topics.map((topic) => (
            <div className="note" key={topic.id}>
              <div className="section-header">
                <div>
                  <p className="eyebrow">ApplyAI Fit</p>
                  <h2>{topic.title}</h2>
                  <p>{topic.source_type}{topic.source_url ? <> · <a href={topic.source_url}>source</a></> : null}</p>
                </div>
                <div>
                  <Badge tone={fitTone(topic.applyai_fit)}>{fitLabel(topic.applyai_fit)}</Badge>
                  <p>{topic.fit_scope} · {topic.classification_source}</p>
                </div>
              </div>

              <p>{topic.summary || "No research summary recorded."}</p>
              <div className="note">
                <strong>Why this qualifies or does not qualify</strong>
                <p>{topic.rationale}</p>
              </div>
              <p><strong>Implementation destination:</strong> {topic.destination}{topic.implementation_target ? ` · ${topic.implementation_target}` : ""}</p>
              <p><strong>Candidate journey stages:</strong> {topic.candidate_journey_stages.length ? topic.candidate_journey_stages.map(pretty).join(" · ") : "No direct candidate stage"}</p>

              <div className="dashboard-grid">
                <div>
                  <p className="eyebrow">Absorb into ApplyAI</p>
                  {topic.qualifying_capabilities.length
                    ? <ul>{topic.qualifying_capabilities.map((capability) => <li key={capability}>{capability}</li>)}</ul>
                    : <p>No capabilities explicitly recorded.</p>}
                </div>
                <div>
                  <p className="eyebrow">Keep separate</p>
                  {topic.excluded_capabilities.length
                    ? <ul>{topic.excluded_capabilities.map((capability) => <li key={capability}>{capability}</li>)}</ul>
                    : <p>No exclusions explicitly recorded.</p>}
                </div>
              </div>

              <div className="button-row">
                <form action={updateReverseEngineeringTopicStatus}>
                  <input type="hidden" name="topic_id" value={topic.id} />
                  <select name="status" defaultValue={topic.status}>
                    {statuses.map((status) => <option key={status} value={status}>{pretty(status)}</option>)}
                  </select>
                  <Button type="submit" size="small" variant="secondary">Update status</Button>
                </form>
                <form action={reclassifyReverseEngineeringTopic}>
                  <input type="hidden" name="topic_id" value={topic.id} />
                  <Button type="submit" size="small" variant="secondary">Re-run classifier</Button>
                </form>
              </div>
              <p>
                <small>
                  Status {pretty(topic.status)} · classifier {topic.classifier_version}
                  {topic.updated_at ? ` · updated ${new Date(topic.updated_at).toLocaleString("en-US")}` : ""}
                </small>
              </p>
            </div>
          ))}
          {!topics.length && <p>No reverse-engineering topics registered yet.</p>}
        </div>
      </Card>
    </main>
  );
}
