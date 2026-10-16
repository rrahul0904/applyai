import Link from "next/link";
import { redirect } from "next/navigation";

import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";

import { addBoardSource, createJobBoard, executePublication, reviewBoardClaim } from "./actions";

type Summary = {
  boards: number;
  public_boards: number;
  pending_claims: number;
  outbound_clicks: number;
  publication_receipts: number;
  published: number;
  dry_runs: number;
  failed_publications: number;
  sponsorship_campaigns: number;
  active_sponsorships: number;
  search_console_clicks: number;
  search_console_impressions: number;
};

type Board = {
  id: string;
  slug: string;
  name: string;
  status: string;
  visibility: string;
  owner_user_id: string | null;
  source_count: number;
  outbound_clicks: number;
  created_at: string;
};

type Claim = {
  id: string;
  board_id: string;
  claimant_user_id: string;
  status: string;
  proof_method: string;
  submitted_at: string;
};

type Publication = {
  id: string;
  job_id: string;
  board_id: string | null;
  channel: string;
  target: string;
  status: string;
  dry_run: boolean;
  external_url: string | null;
  error_summary: string | null;
  created_at: string;
};

function tone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (["ACTIVE", "APPROVED", "PUBLISHED"].includes(status)) return "success";
  if (["PENDING", "DRAFT", "DRY_RUN"].includes(status)) return "warning";
  if (["FAILED", "REJECTED", "DISABLED"].includes(status)) return "danger";
  return "neutral";
}

export default async function JobBoardAdminPage() {
  try {
    await requireOperatorEmail();
  } catch {
    redirect("/dashboard");
  }

  const [summary, boards, claims, publications] = await Promise.all([
    operatorApi<Summary>("job-board-network/summary"),
    operatorApi<Board[]>("job-board-network/boards?limit=100"),
    operatorApi<Claim[]>("job-board-network/claims?status=PENDING&limit=50"),
    operatorApi<Publication[]>("job-board-network/publications?limit=50"),
  ]);

  return (
    <main className="app-main">
      <PageHeader
        eyebrow="Job supply & distribution"
        title="Job Board Network"
        description="Operate niche boards on top of ApplyAI's canonical job graph. Source membership reuses the existing ingestion, deduplication, provenance and freshness pipeline."
        action={<Link className="button button-secondary" href="/job-boards">View public network</Link>}
      />

      <div className="metric-grid">
        <Card><p className="metric-label">Public boards</p><strong className="metric-value">{summary.public_boards}</strong><p>{summary.boards} total</p></Card>
        <Card><p className="metric-label">Outbound clicks</p><strong className="metric-value">{summary.outbound_clicks}</strong><p>Attributed application exits</p></Card>
        <Card><p className="metric-label">Distribution</p><strong className="metric-value">{summary.published}</strong><p>{summary.dry_runs} dry runs · {summary.failed_publications} failed</p></Card>
        <Card><p className="metric-label">Search traffic</p><strong className="metric-value">{summary.search_console_clicks}</strong><p>{summary.search_console_impressions} impressions</p></Card>
      </div>

      <div className="two-column-grid">
        <Card className="detail-section">
          <div className="section-header"><div><h2>Create public board</h2><p>Create the product surface first, then attach existing registered sources.</p></div></div>
          <form action={createJobBoard} className="form-stack">
            <label>Name<input name="name" required placeholder="AI Data Engineering Jobs" /></label>
            <label>Slug<input name="slug" required placeholder="ai-data-engineering" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" /></label>
            <label>Description<textarea name="description" rows={3} placeholder="Curated roles from verified sources." /></label>
            <Button type="submit">Create board</Button>
          </form>
        </Card>

        <Card className="detail-section">
          <div className="section-header"><div><h2>Attach verified source</h2><p>Use the existing job_source_registry UUID. Jobs remain canonical and deduplicated globally.</p></div></div>
          <form action={addBoardSource} className="form-stack">
            <label>Board<select name="board_id" required><option value="">Choose board</option>{boards.map((board) => <option key={board.id} value={board.id}>{board.name}</option>)}</select></label>
            <label>Source registry ID<input name="source_registry_id" required placeholder="UUID from Job Sources" /></label>
            <Button type="submit">Attach source</Button>
          </form>
        </Card>
      </div>

      <Card className="detail-section">
        <div className="section-header"><div><h2>Boards</h2><p>Public surfaces and their source/click footprint.</p></div><Link href="/admin/operations">Manage sources</Link></div>
        <div className="table-scroll"><table className="data-table"><thead><tr><th>Board</th><th>Status</th><th>Sources</th><th>Clicks</th><th>Owner</th></tr></thead><tbody>{boards.map((board) => <tr key={board.id}><td><Link href={`/job-boards/${board.slug}`}>{board.name}</Link><div className="muted">/{board.slug}</div></td><td><Badge tone={tone(board.status)}>{board.status}</Badge></td><td>{board.source_count}</td><td>{board.outbound_clicks}</td><td>{board.owner_user_id ? "Claimed" : "Unclaimed"}</td></tr>)}</tbody></table></div>
      </Card>

      <Card className="detail-section">
        <div className="section-header"><div><h2>Ownership claims</h2><p>{summary.pending_claims} claims await operator verification.</p></div></div>
        {claims.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Board</th><th>Method</th><th>Claimant</th><th>Decision</th></tr></thead><tbody>{claims.map((claim) => <tr key={claim.id}><td>{claim.board_id}</td><td>{claim.proof_method}</td><td>{claim.claimant_user_id}</td><td><div style={{display:"flex",gap:8}}><form action={reviewBoardClaim}><input type="hidden" name="claim_id" value={claim.id}/><input type="hidden" name="decision" value="APPROVED"/><Button type="submit">Approve</Button></form><form action={reviewBoardClaim}><input type="hidden" name="claim_id" value={claim.id}/><input type="hidden" name="decision" value="REJECTED"/><Button type="submit" variant="secondary">Reject</Button></form></div></td></tr>)}</tbody></table></div> : <p className="muted">No pending claims.</p>}
      </Card>

      <Card className="detail-section">
        <div className="section-header"><div><h2>Distribution receipts</h2><p>External publishing is approval-gated and live writes require the runtime publishing switch.</p></div></div>
        {publications.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Channel</th><th>Target</th><th>Status</th><th>Mode</th><th>Action</th></tr></thead><tbody>{publications.map((publication) => <tr key={publication.id}><td>{publication.channel}</td><td>{publication.target}</td><td><Badge tone={tone(publication.status)}>{publication.status}</Badge></td><td>{publication.dry_run ? "Dry run" : "Live"}</td><td>{["DRAFT","APPROVED"].includes(publication.status) ? <form action={executePublication}><input type="hidden" name="publication_id" value={publication.id}/><Button type="submit" variant="secondary">Execute</Button></form> : publication.external_url ? <a href={publication.external_url} target="_blank" rel="noreferrer">Receipt</a> : "—"}</td></tr>)}</tbody></table></div> : <p className="muted">No publication intents yet.</p>}
      </Card>
    </main>
  );
}
