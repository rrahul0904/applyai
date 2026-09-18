import Link from "next/link";
import { redirect } from "next/navigation";

import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";

import { qualifyReferral } from "./actions";

type Metrics = { codes: number; events: number; qualified: number; available_credit_cents: number; };
type ReferralEvent = { id: string; code: string | null; status: string; referrer_user_id: string; referrer_email: string | null; referred_user_id: string; referred_email: string | null; qualified_at: string | null; created_at: string; };

function tone(status: string): "success" | "warning" | "neutral" {
  return status === "CREDITED" || status === "QUALIFIED" ? "success" : status === "PENDING" ? "warning" : "neutral";
}

export default async function ReferralAdminPage() {
  try { await requireOperatorEmail(); } catch { redirect("/dashboard"); }
  const [metrics, events] = await Promise.all([
    operatorApi<Metrics>("referrals/metrics"),
    operatorApi<ReferralEvent[]>("referrals/events?limit=200"),
  ]);
  return (
    <main className="app-main">
      <PageHeader eyebrow="Operator-only" title="Referral Operations" description="Review referral events and issue auditable credits. Candidate referral codes never grant credit until the operator qualification step." action={<Link className="button button-secondary" href="/admin">Back to admin</Link>} />
      <div className="dashboard-grid">
        <Card><p className="eyebrow">Codes</p><h2>{metrics.codes.toLocaleString()}</h2></Card>
        <Card><p className="eyebrow">Referral events</p><h2>{metrics.events.toLocaleString()}</h2></Card>
        <Card><p className="eyebrow">Qualified / credited</p><h2>{metrics.qualified.toLocaleString()}</h2></Card>
        <Card><p className="eyebrow">Available credits</p><h2>${(metrics.available_credit_cents / 100).toFixed(2)}</h2></Card>
      </div>
      <Card className="detail-section">
        <div className="section-header"><div><h2>Referral queue</h2><p>Qualification is idempotent. Re-submitting a credited referral does not duplicate ledger entries.</p></div><Badge>{events.length} shown</Badge></div>
        <div className="list-stack">
          {events.map((event) => (
            <div className="note" key={event.id}>
              <div className="section-header">
                <div><strong>{event.referrer_email ?? event.referrer_user_id}</strong><p>referred {event.referred_email ?? event.referred_user_id} · code {event.code ?? "unavailable"}</p></div>
                <Badge tone={tone(event.status)}>{event.status}</Badge>
              </div>
              <p>Created {new Date(event.created_at).toLocaleString()}</p>
              {event.status === "PENDING" ? (
                <form action={qualifyReferral} className="button-row">
                  <input type="hidden" name="event_id" value={event.id} />
                  <label>Referrer credit USD<input name="referrer_credit_usd" inputMode="decimal" defaultValue="10.00" /></label>
                  <label>Referred credit USD<input name="referred_credit_usd" inputMode="decimal" defaultValue="0.00" /></label>
                  <Button type="submit">Qualify & credit</Button>
                </form>
              ) : null}
            </div>
          ))}
          {!events.length ? <p>No referral events have been recorded yet.</p> : null}
        </div>
      </Card>
    </main>
  );
}
