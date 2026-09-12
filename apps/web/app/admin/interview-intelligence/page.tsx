import Link from "next/link";
import { redirect } from "next/navigation";

import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { operatorApi, requireOperatorEmail } from "@/lib/auth/operator";

import { linkInterviewEvidence, moderateInterviewReport } from "./actions";

type Metrics = {
  questions: number;
  reports: number;
  attempts: number;
  plans: number;
  community_posts: number;
};

type Report = {
  id: string;
  source_type: string;
  company: string | null;
  role: string | null;
  interview_stage: string | null;
  title: string | null;
  body: string;
  license_status: string;
  moderation_status: string;
  created_at: string;
};

type Question = {
  id: string;
  slug: string;
  title: string;
  track: string;
  difficulty: string;
  companies: string[];
  confidence: number;
  report_count: number;
  published: boolean;
};

function tone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "APPROVED" || status === "PUBLISHED") return "success";
  if (status === "REJECTED") return "danger";
  if (status === "REVIEW_REQUIRED") return "warning";
  return "neutral";
}

export default async function InterviewIntelligenceAdminPage() {
  try {
    await requireOperatorEmail();
  } catch {
    redirect("/dashboard");
  }

  const [metrics, reports, questions] = await Promise.all([
    operatorApi<Metrics>("interview-intelligence/metrics"),
    operatorApi<Report[]>("interview-intelligence/reports?moderation_status=REVIEW_REQUIRED&limit=100"),
    operatorApi<Question[]>("interview-intelligence/catalog/questions?limit=250"),
  ]);

  return (
    <main className="app-main">
      <PageHeader
        eyebrow="Interview intelligence control"
        title="Moderation and evidence review"
        description="Candidate submissions are not allowed to become canonical interview questions automatically. Review provenance, approve or reject the report, then explicitly link approved evidence to a clean-room canonical question."
        action={<Link className="button button-secondary" href="/admin">Back to admin</Link>}
      />

      <div className="dashboard-grid">
        <Card className="detail-section"><p className="eyebrow">Canonical questions</p><h2>{metrics.questions}</h2></Card>
        <Card className="detail-section"><p className="eyebrow">Evidence reports</p><h2>{metrics.reports}</h2></Card>
        <Card className="detail-section"><p className="eyebrow">Practice attempts</p><h2>{metrics.attempts}</h2></Card>
        <Card className="detail-section"><p className="eyebrow">Personalized plans</p><h2>{metrics.plans}</h2></Card>
        <Card className="detail-section"><p className="eyebrow">Community posts</p><h2>{metrics.community_posts}</h2></Card>
      </div>

      <Card className="detail-section">
        <div className="section-header"><div><h2>Review queue</h2><p>{reports.length} reports currently require a decision.</p></div><Badge tone={reports.length ? "warning" : "success"}>{reports.length ? "Needs review" : "Clear"}</Badge></div>
        {reports.length ? (
          <div className="activity-feed">
            {reports.map((report) => (
              <article className="activity-item" key={report.id} style={{ alignItems: "flex-start" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
                    <Badge tone={tone(report.moderation_status)}>{report.moderation_status}</Badge>
                    <Badge>{report.source_type}</Badge>
                    <Badge>{report.license_status}</Badge>
                    {report.company ? <Badge tone="info">{report.company}</Badge> : null}
                  </div>
                  <strong>{report.title || `${report.role || "Unknown role"} · ${report.interview_stage || "Unknown round"}`}</strong>
                  <p style={{ whiteSpace: "pre-wrap" }}>{report.body}</p>
                  <small>Submitted {new Date(report.created_at).toLocaleString()}</small>
                </div>
                <div style={{ display: "grid", gap: 10, minWidth: 280 }}>
                  <div style={{ display: "flex", gap: 8 }}>
                    <form action={moderateInterviewReport}><input type="hidden" name="report_id" value={report.id}/><input type="hidden" name="decision" value="APPROVED"/><Button type="submit" size="small">Approve</Button></form>
                    <form action={moderateInterviewReport}><input type="hidden" name="report_id" value={report.id}/><input type="hidden" name="decision" value="REJECTED"/><Button type="submit" size="small" variant="danger">Reject</Button></form>
                  </div>
                  <form action={linkInterviewEvidence} style={{ display: "grid", gap: 8 }}>
                    <input type="hidden" name="report_id" value={report.id}/>
                    <select className="ui-input ui-native-select" name="question_id" defaultValue="" required>
                      <option value="" disabled>Link after approval…</option>
                      {questions.map((question) => <option key={question.id} value={question.id}>{question.track} · {question.title}</option>)}
                    </select>
                    <input className="ui-input" name="confidence" type="number" min="0" max="100" defaultValue="80"/>
                    <Button size="small" variant="secondary" type="submit">Link as evidence</Button>
                  </form>
                </div>
              </article>
            ))}
          </div>
        ) : <p>No reports are waiting for moderation.</p>}
      </Card>

      <Card className="detail-section">
        <div className="section-header"><div><h2>Canonical catalog</h2><p>Clean-room questions available for explicit evidence linking.</p></div></div>
        <div className="activity-feed">
          {questions.slice(0, 50).map((question) => <div className="activity-item" key={question.id}><div><strong>{question.title}</strong><p>{question.track} · {question.difficulty} · {(question.companies || []).join(" · ") || "No company label"}</p></div><div style={{ textAlign: "right" }}><Badge tone={question.published ? "success" : "warning"}>{question.published ? "Published" : "Draft"}</Badge><p>{question.report_count} reports · {question.confidence}% confidence</p></div></div>)}
        </div>
      </Card>
    </main>
  );
}
