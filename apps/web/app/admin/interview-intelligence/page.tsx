import { redirect } from "next/navigation";

import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";
import { createInterviewQuestion, linkInterviewEvidence, moderateInterviewReport, unlinkInterviewEvidence } from "./actions";

type Report = { id: string; company: string | null; role: string | null; interview_stage: string | null; title: string | null; body: string; moderation_status: string; created_at: string };
type Question = { id: string; title: string; track: string; difficulty: string; published: boolean; frequency_score: number; confidence: number; report_count: number; companies: string[] };
type Evidence = { id: string; question_id: string; report_id: string; confidence: number; evidence_notes: string | null };
type Metrics = { questions: number; reports: number; attempts: number; workspaces: number; stories: number; community_posts: number };

export default async function InterviewIntelligenceAdminPage() {
  try {
    await requireOperatorEmail();
  } catch {
    redirect("/dashboard");
  }
  const [metrics, reports, questions, evidence] = await Promise.all([
    operatorApi<Metrics>("interview-intelligence/metrics"),
    operatorApi<Report[]>("interview-intelligence/reports"),
    operatorApi<Question[]>("interview-intelligence-catalog/questions"),
    operatorApi<Evidence[]>("interview-intelligence-catalog/evidence"),
  ]);
  const questionById = new Map(questions.map((item) => [item.id, item]));
  const reportById = new Map(reports.map((item) => [item.id, item]));
  return <div className="page-stack">
    <PageHeader eyebrow="Operator workspace" title="Interview Intelligence" description="Moderate candidate reports, link only approved evidence, and verify that company/frequency aggregates stay reversible." />
    <div className="dashboard-grid">
      <Card><p className="eyebrow">Questions</p><h2>{metrics.questions}</h2></Card>
      <Card><p className="eyebrow">Reports</p><h2>{metrics.reports}</h2></Card>
      <Card><p className="eyebrow">Attempts</p><h2>{metrics.attempts}</h2></Card>
      <Card><p className="eyebrow">Job workspaces</p><h2>{metrics.workspaces}</h2></Card>
      <Card><p className="eyebrow">STAR stories</p><h2>{metrics.stories}</h2></Card>
      <Card><p className="eyebrow">Community posts</p><h2>{metrics.community_posts}</h2></Card>
    </div>

    <Card className="detail-section"><h2>Moderation queue</h2><p>Approved reports remain visible as <strong>APPROVED_UNLINKED</strong> until evidence is attached to a canonical question.</p><div className="list-stack">{reports.map((report) => <div key={report.id} style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}><div className="section-header"><div><strong>{report.title || "Interview report"}</strong><p className="muted">{report.company || "Unknown company"} · {report.role || "Unknown role"} · {report.interview_stage || "Unknown stage"}</p></div><Badge tone={report.moderation_status === "REVIEW_REQUIRED" ? "warning" : "info"}>{report.moderation_status}</Badge></div><p>{report.body}</p>{report.moderation_status === "REVIEW_REQUIRED" ? <div className="button-row"><form action={moderateInterviewReport}><input type="hidden" name="report_id" value={report.id}/><input type="hidden" name="decision" value="APPROVED"/><Button size="small">Approve</Button></form><form action={moderateInterviewReport}><input type="hidden" name="report_id" value={report.id}/><input type="hidden" name="decision" value="REJECTED"/><Button size="small" variant="secondary">Reject</Button></form></div> : report.moderation_status === "APPROVED_UNLINKED" ? <form action={linkInterviewEvidence} className="stack-form"><input type="hidden" name="report_id" value={report.id}/><label>Canonical question<select name="question_id" required defaultValue=""><option value="" disabled>Select a question</option>{questions.map((question) => <option key={question.id} value={question.id}>{question.track} · {question.title}</option>)}</select></label><label>Evidence confidence<input name="confidence" type="number" min="0" max="100" defaultValue="75"/></label><label>Evidence notes<textarea name="evidence_notes" rows={3}/></label><Button size="small">Link evidence</Button></form> : null}</div>)}{reports.length === 0 ? <p className="muted">No reports currently require moderation or linking.</p> : null}</div></Card>

    <Card className="detail-section"><h2>Linked evidence</h2><p>Removing evidence recomputes frequency, companies, confidence and recency from the remaining links plus the clean-room baseline.</p><div className="list-stack">{evidence.map((item) => <div key={item.id} className="section-header" style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}><div><strong>{questionById.get(item.question_id)?.title ?? item.question_id}</strong><p className="muted">Report: {reportById.get(item.report_id)?.title ?? item.report_id} · confidence {item.confidence}%</p></div><form action={unlinkInterviewEvidence}><input type="hidden" name="evidence_id" value={item.id}/><Button size="small" variant="secondary">Unlink</Button></form></div>)}{evidence.length === 0 ? <p className="muted">No report evidence linked yet.</p> : null}</div></Card>

    <Card className="detail-section"><h2>Add clean-room question</h2><form action={createInterviewQuestion} className="stack-form"><label>Title<input name="title" required/></label><div className="dashboard-grid"><label>Track<select name="track" defaultValue="BEHAVIORAL"><option>CODING</option><option>SQL</option><option>SYSTEM_DESIGN</option><option>ML_SYSTEM_DESIGN</option><option>OOD</option><option>BEHAVIORAL</option></select></label><label>Difficulty<select name="difficulty" defaultValue="MEDIUM"><option>EASY</option><option>MEDIUM</option><option>HARD</option></select></label><label>Baseline frequency<input name="frequency_score" type="number" min="0" max="100" defaultValue="0"/></label></div><label>Summary<textarea name="summary" rows={3} required/></label><label>Prompt<textarea name="prompt" rows={5} required/></label><label>Companies (one per line)<textarea name="companies" rows={3}/></label><label>Skills (one per line)<textarea name="skills" rows={3}/></label><label>Patterns (one per line)<textarea name="patterns" rows={3}/></label><label>Hints (one per line)<textarea name="hints" rows={4}/></label><label>Follow-ups (one per line)<textarea name="follow_ups" rows={3}/></label><label>Solution outline (one per line)<textarea name="solution_outline" rows={4}/></label><label><input name="published" type="checkbox"/> Publish immediately</label><Button type="submit">Create question</Button></form></Card>
  </div>;
}
