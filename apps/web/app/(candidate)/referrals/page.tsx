"use client";

import { Copy, Gift, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, Card, Input, PageHeader } from "@/components/ui";

type ReferralSummary = {
  code: string;
  enabled: boolean;
  referrals: Array<{ id: string; status: string; created_at: string; qualified_at: string | null }>;
  available_credit_cents: number;
  ledger: Array<{ id: string; amount_cents: number; entry_type: string; status: string; created_at: string; applied_at: string | null }>;
};

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend/referrals${path}`, { ...init, headers: init.body ? { "content-type": "application/json", ...init.headers } : init.headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
    throw new Error(body?.error?.message ?? "Referral request failed");
  }
  return response.json() as Promise<T>;
}

export default function ReferralsPage() {
  const [summary, setSummary] = useState<ReferralSummary | null>(null);
  const [claimCode, setClaimCode] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => { api<ReferralSummary>("/me").then(setSummary).catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : "Could not load referrals")); }, []);

  async function claim() {
    setMessage(null);
    try {
      const result = await api<{ status: string; already_claimed: boolean }>("/claim", { method: "POST", body: JSON.stringify({ code: claimCode }) });
      setMessage(result.already_claimed ? `Referral already recorded (${result.status}).` : `Referral recorded (${result.status}).`);
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "Could not claim referral"); }
  }

  return <div style={{ display: "grid", gap: 20 }}>
    <PageHeader eyebrow="Growth" title="Invite people you trust." description="Your referral history and credit ledger are durable and auditable. Reward amounts are controlled by ApplyAI policy, not copied from another product." />
    {!summary ? <Card style={{ padding: 24 }}>Loading referral account…</Card> : <>
      <div className="dashboard-grid">
        <Card className="detail-section"><Gift size={18}/><p className="eyebrow">Available credit</p><h2>${(summary.available_credit_cents / 100).toFixed(2)}</h2></Card>
        <Card className="detail-section"><Users size={18}/><p className="eyebrow">Referrals</p><h2>{summary.referrals.length}</h2></Card>
        <Card className="detail-section"><p className="eyebrow">Your code</p><h2>{summary.code}</h2><Button size="small" variant="secondary" onClick={() => navigator.clipboard.writeText(summary.code)}><Copy size={14}/> Copy</Button></Card>
      </div>
      <Card className="detail-section"><h2>Claim a referral</h2><p>If someone invited you, enter their code once. Self-referrals and duplicate claims are blocked.</p><div style={{ display: "flex", gap: 10, maxWidth: 520 }}><Input value={claimCode} onChange={(event) => setClaimCode(event.target.value)} placeholder="Referral code"/><Button onClick={claim} disabled={!claimCode.trim()}>Claim</Button></div>{message ? <p>{message}</p> : null}</Card>
      <Card className="detail-section"><h2>Credit ledger</h2>{summary.ledger.length ? <div className="activity-feed">{summary.ledger.map((entry) => <div key={entry.id} className="activity-item"><div><strong>{entry.entry_type.replaceAll("_", " ")}</strong><p>${(entry.amount_cents / 100).toFixed(2)} · {new Date(entry.created_at).toLocaleDateString()}</p></div><Badge tone={entry.status === "AVAILABLE" ? "success" : "neutral"}>{entry.status}</Badge></div>)}</div> : <p>No referral credits yet.</p>}</Card>
    </>}
  </div>;
}
