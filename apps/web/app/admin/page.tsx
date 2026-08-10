import { redirect } from "next/navigation";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";
import {
  cancelAgentRun,
  disableAgentDefinition,
  disableJobSource,
  discoverOrganizationJobs,
  dispatchEngagement,
  enableAgentDefinition,
  enableJobSource,
  refreshJobSource,
  retryAgentRun,
  suspendOrganization,
  verifyOrganization,
} from "./actions";

type Metrics = Record<string, number>;
type Organization = { id: string; name: string; slug: string; verification_status: string; created_at: string };
type Evaluation = { dataset_version: string; aggregate: Record<string, number | null> };
type JobSupplyQuality = {
  organizations_total: number;
  organizations_with_domains: number;
  organizations_with_career_sites: number;
  organizations_with_detected_ats: number;
  sources_total: number;
  sources_enabled: number;
  sources_healthy: number;
  sources_failing: number;
  canonical_active_jobs: number;
  canonical_stale_jobs: number;
  new_jobs: number;
  apply_url_validity_percentage: number | null;
  freshness: Record<string, number>;
};
type JobSupplyOverview = {
  status: string;
  quality: JobSupplyQuality;
  pending_dedup_reviews: number;
};
type JobSupplySource = {
  id: string;
  source_type: string;
  source_name: string;
  source_identity: string;
  trust_level: string;
  health_status: string;
  enabled: boolean;
  crawl_allowed: boolean;
  last_job_count: number;
  last_change_count: number;
  last_success_at: string | null;
  next_run_at: string;
};
type JobSupplyProvider = {
  provider_key: string;
  display_name: string;
  access_mode: string;
  implementation_status: string;
  allowed_for_automated_ingestion: boolean;
  requires_partnership: boolean;
  requires_credentials: boolean;
};
type JobSupplyOrganization = {
  id: string;
  canonical_name: string;
  canonical_domain: string | null;
  organization_type: string;
  careers_url: string | null;
  ats_provider: string | null;
  source_status: string;
};
type AgentOverview = {
  definitions: number;
  tools: number;
  runs_by_status: Record<string, number>;
  failures_24h: number;
  pending_approvals: number;
  cost_usd_24h: number;
};
type AgentDefinition = {
  name: string;
  version: string;
  description: string;
  execution_class: "READ" | "PREPARE" | "EXECUTE";
  allowed_tools: string[];
  denied_tools: string[];
  queue_class: string;
  max_steps: number;
  timeout_seconds: number;
  max_cost_usd: number;
  definition_enabled: boolean;
  enabled_override: boolean | null;
  paused_at: string | null;
  policy_reason: string | null;
};
type AgentRun = {
  id: string;
  candidate_id: string;
  job_id: string | null;
  agent_name: string;
  agent_version: string;
  workflow_id: string | null;
  status: string;
  execution_class: string;
  queue_class: string;
  priority: number;
  attempt_count: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  provider: string | null;
  model: string | null;
  current_step: string | null;
  error_code: string | null;
};
type AgentCost = {
  days: number;
  groups: Array<{
    agent_name: string;
    provider: string | null;
    model: string | null;
    runs: number;
    cost_usd: number;
    input_tokens: number;
    output_tokens: number;
  }>;
};

function metric(value: number | null | undefined) {
  return value == null ? "Not measured" : value.toLocaleString();
}

function agentTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "SUCCEEDED") return "success";
  if (status === "FAILED_TERMINAL" || status === "FAILED_RETRYABLE") return "danger";
  if (status === "WAITING_FOR_APPROVAL" || status === "QUEUED" || status === "CLAIMED") return "warning";
  return "neutral";
}

export default async function AdminPage() {
  try { await requireOperatorEmail(); } catch { redirect("/dashboard"); }
  const [
    metrics,
    organizations,
    evaluation,
    jobSupply,
    sources,
    providers,
    jobOrganizations,
    agentOverview,
    agentDefinitions,
    agentRuns,
    agentFailures,
    agentCost,
  ] = await Promise.all([
    operatorApi<Metrics>("platform/metrics"),
    operatorApi<Organization[]>("platform/organizations"),
    operatorApi<Evaluation>("ai-evaluation/golden"),
    operatorApi<JobSupplyOverview>("job-supply/overview"),
    operatorApi<JobSupplySource[]>("job-supply/sources?limit=20"),
    operatorApi<JobSupplyProvider[]>("job-supply/providers?limit=30"),
    operatorApi<JobSupplyOrganization[]>("job-supply/organizations?limit=20"),
    operatorApi<AgentOverview>("agents/overview"),
    operatorApi<AgentDefinition[]>("agents/definitions"),
    operatorApi<AgentRun[]>("agents/runs?limit=20"),
    operatorApi<AgentRun[]>("agents/failures?limit=10"),
    operatorApi<AgentCost>("agents/cost?days=7"),
  ]);
  const q = jobSupply.quality;
  return <main className="app-main">
    <PageHeader eyebrow="Operator-only" title="ApplyAI Operations" description="Platform health, governed agents, job supply, employer trust, candidate engagement and AI evaluation without exposing the internal operator token to the browser." action={<form action={dispatchEngagement}><Button type="submit">Dispatch due engagement</Button></form>} />

    <div className="dashboard-grid">{Object.entries(metrics).map(([key,value]) => <Card key={key}><p className="eyebrow">{key.replaceAll("_"," ")}</p><h2>{value}</h2></Card>)}</div>

    <Card className="detail-section">
      <div className="section-header"><div><h2>Governed Agent Runtime</h2><p>Durable, permissioned career workflows. Agent count is not a success metric; failed runs, approvals and cost are surfaced directly.</p></div><Badge tone={agentOverview.failures_24h === 0 ? "success" : "warning"}>{agentOverview.definitions} definitions</Badge></div>
      <div className="dashboard-grid">
        <div><p className="eyebrow">Runtime states</p><h2>{metric(agentOverview.runs_by_status.SUCCEEDED ?? 0)} succeeded</h2><p>{metric(agentOverview.runs_by_status.RUNNING ?? 0)} running · {metric(agentOverview.runs_by_status.QUEUED ?? 0)} queued</p></div>
        <div><p className="eyebrow">Failures</p><h2>{metric(agentOverview.failures_24h)}</h2><p>Last 24 hours</p></div>
        <div><p className="eyebrow">Approvals</p><h2>{metric(agentOverview.pending_approvals)}</h2><p>Pending EXECUTE-class approvals</p></div>
        <div><p className="eyebrow">Agent cost</p><h2>${agentOverview.cost_usd_24h.toFixed(4)}</h2><p>Measured provider cost in the last 24 hours</p></div>
      </div>
      <div className="list-stack">{agentDefinitions.map((definition) => {
        const enabled = definition.definition_enabled && definition.enabled_override !== false && !definition.paused_at;
        return <div className="note" key={`${definition.name}:${definition.version}`}>
          <div className="section-header"><div><strong>{definition.name} {definition.version}</strong><p>{definition.description}</p></div><Badge tone={enabled ? "success" : "danger"}>{enabled ? "ENABLED" : "PAUSED"}</Badge></div>
          <p>{definition.execution_class} · {definition.queue_class} · max ${definition.max_cost_usd.toFixed(2)} · {definition.allowed_tools.length} tools</p>
          <p>{definition.allowed_tools.join(" · ")}</p>
          <div className="button-row">
            {enabled ? <form action={disableAgentDefinition}><input type="hidden" name="agent_name" value={definition.name}/><input type="hidden" name="agent_version" value={definition.version}/><Button variant="secondary" size="small" type="submit">Pause agent</Button></form> : <form action={enableAgentDefinition}><input type="hidden" name="agent_name" value={definition.name}/><input type="hidden" name="agent_version" value={definition.version}/><Button size="small" type="submit">Enable agent</Button></form>}
          </div>
        </div>;
      })}</div>
    </Card>

    <Card className="detail-section">
      <div className="section-header"><div><h2>Recent agent runs</h2><p>Each run is durable and auditable. Retry is restricted to failed runs; cancel is restricted by the state machine.</p></div><Badge>{agentRuns.length} shown</Badge></div>
      <div className="list-stack">{agentRuns.map((run) => <div className="note" key={run.id}>
        <div className="section-header"><div><strong>{run.agent_name} {run.agent_version}</strong><p>{run.workflow_id ?? "No workflow"} · job {run.job_id ?? "n/a"}</p></div><Badge tone={agentTone(run.status)}>{run.status}</Badge></div>
        <p>{run.execution_class} · {run.queue_class} · attempt {run.attempt_count} · {run.provider ?? "provider pending"}/{run.model ?? "model pending"}</p>
        <p>{run.input_tokens + run.output_tokens} tokens · ${run.cost_usd.toFixed(4)}{run.error_code ? ` · ${run.error_code}` : ""}</p>
        <div className="button-row">
          {(run.status === "FAILED_RETRYABLE" || run.status === "FAILED_TERMINAL") && <form action={retryAgentRun}><input type="hidden" name="run_id" value={run.id}/><Button size="small" type="submit">Retry</Button></form>}
          {!["SUCCEEDED","FAILED_TERMINAL","CANCELLED","EXPIRED"].includes(run.status) && <form action={cancelAgentRun}><input type="hidden" name="run_id" value={run.id}/><Button variant="secondary" size="small" type="submit">Cancel</Button></form>}
        </div>
      </div>)}</div>
      {agentFailures.length > 0 && <div className="note"><strong>Failure queue</strong><p>{agentFailures.map((run) => `${run.agent_name}: ${run.error_code ?? run.status}`).join(" · ")}</p></div>}
      <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(agentCost.groups,null,2)}</pre>
    </Card>

    <Card className="detail-section">
      <div className="section-header"><div><h2>Global job supply</h2><p>Measured catalog and source health. Synthetic scale evidence is never presented here as live inventory.</p></div><Badge tone={q.sources_failing === 0 ? "success" : "warning"}>{jobSupply.status}</Badge></div>
      <div className="dashboard-grid">
        <div><p className="eyebrow">Organizations</p><h2>{metric(q.organizations_total)}</h2><p>{metric(q.organizations_with_domains)} domains · {metric(q.organizations_with_career_sites)} career sites</p></div>
        <div><p className="eyebrow">Active jobs</p><h2>{metric(q.canonical_active_jobs)}</h2><p>{metric(q.new_jobs)} created in the measured window · {metric(q.canonical_stale_jobs)} stale</p></div>
        <div><p className="eyebrow">Sources</p><h2>{metric(q.sources_healthy)} healthy</h2><p>{metric(q.sources_enabled)} enabled · {metric(q.sources_failing)} failing</p></div>
        <div><p className="eyebrow">Apply URLs</p><h2>{q.apply_url_validity_percentage == null ? "Not measured" : `${q.apply_url_validity_percentage}%`}</h2><p>{jobSupply.pending_dedup_reviews} dedup review candidates</p></div>
      </div>
      <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(q.freshness,null,2)}</pre>
    </Card>

    <Card className="detail-section">
      <div className="section-header"><div><h2>Job source registry</h2><p>Highest-priority sources first. Refresh schedules a source immediately; it does not perform an external fetch in the browser request.</p></div><Badge>{sources.length} shown</Badge></div>
      <div className="list-stack">{sources.map((source)=><div className="note" key={source.id}>
        <div className="section-header"><div><strong>{source.source_name}</strong><p>{source.source_type} · {source.source_identity} · {source.trust_level}</p></div><Badge tone={source.health_status === "HEALTHY" ? "success" : source.health_status === "FAILING" ? "danger" : "warning"}>{source.health_status}</Badge></div>
        <p>{source.last_job_count} jobs · {source.last_change_count} changes · last success {source.last_success_at ?? "never"}</p>
        <div className="button-row">
          {source.enabled ? <form action={disableJobSource}><input type="hidden" name="source_id" value={source.id}/><Button variant="secondary" size="small" type="submit">Disable</Button></form> : <form action={enableJobSource}><input type="hidden" name="source_id" value={source.id}/><Button size="small" type="submit">Enable</Button></form>}
          <form action={refreshJobSource}><input type="hidden" name="source_id" value={source.id}/><Button variant="secondary" size="small" type="submit" disabled={!source.enabled || !source.crawl_allowed}>Schedule refresh</Button></form>
        </div>
      </div>)}</div>
    </Card>

    <Card className="detail-section">
      <div className="section-header"><div><h2>Organization coverage</h2><p>Organizations can be queued for bounded, policy-aware career-source discovery.</p></div><Badge>{jobOrganizations.length} shown</Badge></div>
      <div className="list-stack">{jobOrganizations.map((org)=><div className="note" key={org.id}>
        <div className="section-header"><div><strong>{org.canonical_name}</strong><p>{org.organization_type} · {org.canonical_domain ?? "domain not loaded"} · ATS {org.ats_provider ?? "not detected"}</p></div><Badge tone={org.source_status === "ACTIVE" || org.source_status === "VERIFIED" ? "success" : org.source_status === "BLOCKED" ? "danger" : "warning"}>{org.source_status}</Badge></div>
        <p>{org.careers_url ?? "Career site not discovered"}</p>
        <form action={discoverOrganizationJobs}><input type="hidden" name="organization_profile_id" value={org.id}/><Button size="small" type="submit" disabled={!org.canonical_domain && !org.careers_url}>Discover jobs</Button></form>
      </div>)}</div>
    </Card>

    <Card className="detail-section">
      <div className="section-header"><div><h2>Provider policy</h2><p>Marketplace providers stay partnership-gated unless an authorized feed or API is configured.</p></div><Badge>{providers.length} shown</Badge></div>
      <div className="list-stack">{providers.map((provider)=><div className="note" key={provider.provider_key}>
        <div className="section-header"><div><strong>{provider.display_name}</strong><p>{provider.access_mode}</p></div><Badge tone={provider.allowed_for_automated_ingestion ? "success" : provider.requires_partnership ? "warning" : "neutral"}>{provider.implementation_status}</Badge></div>
        <p>{provider.requires_credentials ? "Credentials required · " : ""}{provider.requires_partnership ? "Partnership required" : provider.allowed_for_automated_ingestion ? "Automated ingestion permitted by source policy" : "Not enabled for automated ingestion"}</p>
      </div>)}</div>
    </Card>

    <Card className="detail-section"><div className="section-header"><div><h2>AI evaluation gate</h2><p>{evaluation.dataset_version}</p></div><Badge tone={(evaluation.aggregate.unsupported_reference_count ?? 1) === 0 ? "success" : "danger"}>Unsupported refs {evaluation.aggregate.unsupported_reference_count ?? "n/a"}</Badge></div><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(evaluation.aggregate,null,2)}</pre></Card>

    <Card className="detail-section"><h2>Employer verification</h2><div className="list-stack">{organizations.map((org)=><div className="note" key={org.id}><div className="section-header"><div><strong>{org.name}</strong><p>{org.slug}</p></div><Badge tone={org.verification_status === "VERIFIED" ? "success" : org.verification_status === "SUSPENDED" ? "danger" : "warning"}>{org.verification_status}</Badge></div><div className="button-row"><form action={verifyOrganization}><input type="hidden" name="organization_id" value={org.id}/><Button size="small" type="submit">Verify</Button></form><form action={suspendOrganization}><input type="hidden" name="organization_id" value={org.id}/><Button variant="secondary" size="small" type="submit">Suspend</Button></form></div></div>)}</div></Card>
  </main>;
}