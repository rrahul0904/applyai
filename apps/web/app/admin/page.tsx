import { redirect } from "next/navigation";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";
import { dispatchEngagement, suspendOrganization, verifyOrganization } from "./actions";

type Metrics = Record<string, number>;
type Organization = { id: string; name: string; slug: string; verification_status: string; created_at: string };
type Evaluation = { dataset_version: string; aggregate: Record<string, number | null> };

export default async function AdminPage() {
  try { await requireOperatorEmail(); } catch { redirect("/dashboard"); }
  const [metrics, organizations, evaluation] = await Promise.all([
    operatorApi<Metrics>("platform/metrics"),
    operatorApi<Organization[]>("platform/organizations"),
    operatorApi<Evaluation>("ai-evaluation/golden"),
  ]);
  return <main className="app-main">
    <PageHeader eyebrow="Operator-only" title="ApplyAI Operations" description="Source health, employer trust, candidate engagement, AI evaluation and platform counters without exposing the internal operator token to the browser." action={<form action={dispatchEngagement}><Button type="submit">Dispatch due engagement</Button></form>} />
    <div className="dashboard-grid">{Object.entries(metrics).map(([key,value]) => <Card key={key}><p className="eyebrow">{key.replaceAll("_"," ")}</p><h2>{value}</h2></Card>)}</div>
    <Card className="detail-section"><div className="section-header"><div><h2>AI evaluation gate</h2><p>{evaluation.dataset_version}</p></div><Badge tone={(evaluation.aggregate.unsupported_reference_count ?? 1) === 0 ? "success" : "danger"}>Unsupported refs {evaluation.aggregate.unsupported_reference_count ?? "n/a"}</Badge></div><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(evaluation.aggregate,null,2)}</pre></Card>
    <Card className="detail-section"><h2>Employer verification</h2><div className="list-stack">{organizations.map((org)=><div className="note" key={org.id}><div className="section-header"><div><strong>{org.name}</strong><p>{org.slug}</p></div><Badge tone={org.verification_status === "VERIFIED" ? "success" : org.verification_status === "SUSPENDED" ? "danger" : "warning"}>{org.verification_status}</Badge></div><div className="button-row"><form action={verifyOrganization}><input type="hidden" name="organization_id" value={org.id}/><Button size="small" type="submit">Verify</Button></form><form action={suspendOrganization}><input type="hidden" name="organization_id" value={org.id}/><Button variant="secondary" size="small" type="submit">Suspend</Button></form></div></div>)}</div></Card>
  </main>;
}
