"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, MessageSquareText, Send, Sparkles, Target } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, EmptyState, Field, NativeSelect, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { InterviewCodeRunner } from "@/components/interview-code-runner";
import { interviewIntelligenceApi, type InterviewQuestion } from "@/lib/api/interview-intelligence-client";

const TRACKS = ["", "CODING", "SQL", "SYSTEM_DESIGN", "ML_SYSTEM_DESIGN", "OOD", "BEHAVIORAL"];

function scoreTone(score: number) {
  if (score >= 80) return "success" as const;
  if (score >= 60) return "info" as const;
  return "warning" as const;
}

function QuestionPractice({ question }: { question: InterviewQuestion }) {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState("");
  const [hintLevel, setHintLevel] = useState(0);
  const [hint, setHint] = useState<string | null>(null);
  const [result, setResult] = useState<{ score: number; feedback: Record<string, unknown> } | null>(null);
  const coach = useMutation({
    mutationFn: () => interviewIntelligenceApi.coach(question.id, answer, hintLevel),
    onSuccess: (data) => { setHint(data.hint); setHintLevel(data.next_level); },
  });
  const attempt = useMutation({
    mutationFn: () => interviewIntelligenceApi.attempt({ question_id: question.id, answer_text: answer }),
    onSuccess: async (data) => {
      setResult({ score: data.score, feedback: data.feedback });
      await queryClient.invalidateQueries({ queryKey: ["interview-intelligence-progress"] });
      toast.success("Practice attempt saved");
    },
  });
  return <Card className="detail-section">
    <div className="section-header"><div><p className="eyebrow">{question.track.replaceAll("_", " ")} · {question.difficulty}</p><h2>{question.title}</h2><p>{question.summary}</p></div><div className="button-row"><Badge tone="info">Frequency {question.frequency_score}</Badge><Badge tone={question.confidence >= 70 ? "success" : "neutral"}>Confidence {question.confidence}%</Badge></div></div>
    <p style={{ fontSize: 18 }}><strong>{question.prompt}</strong></p>
    {question.skills.length ? <p className="muted">Focus: {question.skills.join(" · ")}</p> : null}
    <Field label="Your answer" htmlFor={`answer-${question.id}`}><Textarea id={`answer-${question.id}`} rows={9} value={answer} onChange={(event) => setAnswer(event.target.value)} /></Field>
    <div className="button-row"><Button onClick={() => attempt.mutate()} disabled={!answer.trim() || attempt.isPending}><Target size={15}/>Score attempt</Button><Button variant="secondary" onClick={() => coach.mutate()} disabled={coach.isPending}><Sparkles size={15}/>Get staged hint</Button></div>
    {hint ? <Card style={{ marginTop: 14 }}><p className="eyebrow">Hint</p><p>{hint}</p></Card> : null}
    {result ? <Card style={{ marginTop: 14 }}><div className="section-header"><h3>Practice result</h3><Badge tone={scoreTone(result.score)}>{result.score}%</Badge></div><pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{JSON.stringify(result.feedback, null, 2)}</pre></Card> : null}
    {question.solution_outline.length ? <details style={{ marginTop: 16 }}><summary>Review solution outline</summary><ol>{question.solution_outline.map((item) => <li key={item}>{item}</li>)}</ol></details> : null}
  </Card>;
}

export function InterviewIntelligenceHub() {
  const queryClient = useQueryClient();
  const [track, setTrack] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState({ company: "", role: "", interview_stage: "", title: "", body: "" });
  const [community, setCommunity] = useState({ company: "", title: "", body: "" });
  const queryString = track ? `track=${track}` : "";
  const questions = useQuery({ queryKey: ["interview-intelligence-questions", track], queryFn: ({ signal }) => interviewIntelligenceApi.questions(queryString, signal) });
  const companies = useQuery({ queryKey: ["interview-intelligence-companies"], queryFn: ({ signal }) => interviewIntelligenceApi.companies(signal) });
  const progress = useQuery({ queryKey: ["interview-intelligence-progress"], queryFn: ({ signal }) => interviewIntelligenceApi.progress(signal) });
  const communityFeed = useQuery({ queryKey: ["interview-intelligence-community"], queryFn: ({ signal }) => interviewIntelligenceApi.community(signal) });
  const selected = useMemo(() => questions.data?.items.find((item) => item.id === selectedId) ?? questions.data?.items[0] ?? null, [questions.data, selectedId]);
  const submitReport = useMutation({
    mutationFn: () => interviewIntelligenceApi.submitReport({ ...report, company: report.company || null, role: report.role || null, interview_stage: report.interview_stage || null, title: report.title || null }),
    onSuccess: () => { setReport({ company: "", role: "", interview_stage: "", title: "", body: "" }); toast.success("Interview report submitted for moderation"); },
  });
  const createCommunity = useMutation({
    mutationFn: () => interviewIntelligenceApi.createCommunity({ ...community, company: community.company || null, category: "INTERVIEW_EXPERIENCE" }),
    onSuccess: async () => { setCommunity({ company: "", title: "", body: "" }); await queryClient.invalidateQueries({ queryKey: ["interview-intelligence-community"] }); toast.success("Community post published"); },
  });
  if (questions.isLoading || companies.isLoading || progress.isLoading) return <Skeleton className="page-skeleton" />;
  return <div className="page-stack">
    <PageHeader eyebrow="ApplyAI Prepare" title="Interview Intelligence" description="Clean-room company patterns, question intelligence, staged coaching, durable practice, candidate reports and community evidence. Embedded arbitrary code execution stays outside ApplyAI behind an isolated integration boundary." />
    <div className="dashboard-grid">
      <Card><p className="eyebrow">Question bank</p><h2>{questions.data?.total ?? 0}</h2><p>Published clean-room prompts</p></Card>
      <Card><p className="eyebrow">Practice attempts</p><h2>{progress.data?.total_attempts ?? 0}</h2><p>Durable across sessions</p></Card>
      <Card><p className="eyebrow">Company collections</p><h2>{companies.data?.length ?? 0}</h2><p>Evidence appears only after approved reports are linked</p></Card>
    </div>
    <div className="detail-grid">
      <div className="detail-main">
        <Card className="detail-section"><div className="section-header"><div><h2>Question intelligence</h2><p>Filter by track, then practice with progressive hints.</p></div><NativeSelect aria-label="Track" value={track} onChange={(event) => setTrack(event.target.value)}>{TRACKS.map((item) => <option key={item || "all"} value={item}>{item ? item.replaceAll("_", " ") : "All tracks"}</option>)}</NativeSelect></div><div className="list-stack">{questions.data?.items.map((item) => <button key={item.id} type="button" onClick={() => setSelectedId(item.id)} style={{ textAlign: "left", border: "1px solid var(--border)", borderRadius: 12, padding: 14, background: selected?.id === item.id ? "var(--surface-raised)" : "transparent", color: "inherit", cursor: "pointer" }}><div className="section-header"><strong>{item.title}</strong><Badge>{item.difficulty}</Badge></div><p className="muted">{item.track.replaceAll("_", " ")} · frequency {item.frequency_score} · confidence {item.confidence}%</p></button>)}{!questions.data?.items.length ? <EmptyState title="No questions match" description="Try another track." /> : null}</div></Card>
        {selected ? <QuestionPractice question={selected} /> : null}
        {selected?.track === "CODING" ? <InterviewCodeRunner /> : null}
        <Card className="detail-section"><div className="section-header"><div><h2>Candidate interview reports</h2><p>Submit firsthand interview experience. Reports are fingerprinted and require operator moderation before influencing question evidence.</p></div><Send size={20}/></div><div className="dashboard-grid"><Field label="Company" htmlFor="report-company"><input id="report-company" value={report.company} onChange={(event) => setReport((value) => ({ ...value, company: event.target.value }))} /></Field><Field label="Role" htmlFor="report-role"><input id="report-role" value={report.role} onChange={(event) => setReport((value) => ({ ...value, role: event.target.value }))} /></Field><Field label="Interview stage" htmlFor="report-stage"><input id="report-stage" value={report.interview_stage} onChange={(event) => setReport((value) => ({ ...value, interview_stage: event.target.value }))} /></Field></div><Field label="Title" htmlFor="report-title"><input id="report-title" value={report.title} onChange={(event) => setReport((value) => ({ ...value, title: event.target.value }))} /></Field><Field label="What happened?" htmlFor="report-body"><Textarea id="report-body" rows={7} value={report.body} onChange={(event) => setReport((value) => ({ ...value, body: event.target.value }))} /></Field><Button onClick={() => submitReport.mutate()} disabled={report.body.trim().length < 20 || submitReport.isPending}>Submit for moderation</Button></Card>
        <Card className="detail-section"><div className="section-header"><div><h2>Candidate community</h2><p>Share interview experience without changing canonical question evidence.</p></div><MessageSquareText size={20}/></div><Field label="Company (optional)" htmlFor="community-company"><input id="community-company" value={community.company} onChange={(event) => setCommunity((value) => ({ ...value, company: event.target.value }))} /></Field><Field label="Title" htmlFor="community-title"><input id="community-title" value={community.title} onChange={(event) => setCommunity((value) => ({ ...value, title: event.target.value }))} /></Field><Field label="Post" htmlFor="community-body"><Textarea id="community-body" rows={5} value={community.body} onChange={(event) => setCommunity((value) => ({ ...value, body: event.target.value }))} /></Field><Button onClick={() => createCommunity.mutate()} disabled={community.title.trim().length < 5 || community.body.trim().length < 20 || createCommunity.isPending}>Publish post</Button><div className="list-stack" style={{ marginTop: 18 }}>{(communityFeed.data ?? []).map((raw) => { const item = raw as { id: string; title: string; body: string; company?: string | null; reaction_count?: number }; return <div key={item.id} style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}><strong>{item.title}</strong><p className="muted">{item.company || "General"} · {item.reaction_count ?? 0} reactions</p><p>{item.body}</p></div>; })}</div></Card>
      </div>
      <aside className="detail-aside"><Card className="sticky-actions"><h2><Building2 size={18} style={{ verticalAlign: "middle", marginRight: 7 }}/>Company intelligence</h2>{(companies.data ?? []).length ? <div className="list-stack">{companies.data?.slice(0, 20).map((item) => <div key={item.slug}><strong>{item.name}</strong><p className="muted">{item.question_count} questions · {item.report_count} linked reports</p></div>)}</div> : <p className="muted">Company-specific evidence appears only after approved candidate reports are linked by an operator. The seeded question bank intentionally makes no company-specific claims.</p>}<h3>Track progress</h3>{Object.entries(progress.data?.by_track ?? {}).map(([name, stats]) => <div key={name} className="section-header"><span>{name.replaceAll("_", " ")}</span><Badge tone={scoreTone(stats.average_score)}>{stats.average_score}% · {stats.attempts}</Badge></div>)}</Card></aside>
    </div>
  </div>;
}
