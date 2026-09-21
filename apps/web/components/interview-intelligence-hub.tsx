"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, MessageSquareText, Search, Send, Sparkles, Target } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, EmptyState, Field, NativeSelect, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { InterviewCodeRunner } from "@/components/interview-code-runner";
import { interviewIntelligenceApi, type InterviewCommunityPost, type InterviewProgress, type InterviewQuestion } from "@/lib/api/interview-intelligence-client";

const TRACKS = ["", "CODING", "SQL", "SYSTEM_DESIGN", "ML_SYSTEM_DESIGN", "OOD", "BEHAVIORAL"];
const DIFFICULTIES = ["", "EASY", "MEDIUM", "HARD"];

function scoreTone(score: number) {
  if (score >= 80) return "success" as const;
  if (score >= 60) return "info" as const;
  return "warning" as const;
}

function recencyLabel(value: string | null) {
  if (!value) return "Clean-room baseline";
  const then = new Date(value);
  const days = Math.max(0, Math.floor((Date.now() - then.getTime()) / 86_400_000));
  if (days === 0) return "Reported today";
  if (days === 1) return "Reported 1 day ago";
  return `Reported ${days} days ago`;
}

function questionGuidance(track: string) {
  if (track === "CODING") {
    return [
      "Explain correctness and edge cases before optimizing.",
      "State time and space complexity explicitly.",
      "Discuss code quality, failure behavior, and test coverage.",
    ];
  }
  if (track === "SQL") {
    return [
      "State schema and data-grain assumptions.",
      "Explain correctness for nulls, duplicates, and boundary cases.",
      "Discuss query-plan, indexing, and scale implications.",
    ];
  }
  if (track === "SYSTEM_DESIGN" || track === "ML_SYSTEM_DESIGN") {
    return [
      "Clarify functional and non-functional requirements.",
      "Make data model, API, reliability, and scaling trade-offs explicit.",
      "Call out bottlenecks, failure modes, observability, and verification.",
    ];
  }
  if (track === "OOD") {
    return [
      "Name responsibilities and boundaries before classes.",
      "Explain interfaces, extensibility, invariants, and failure behavior.",
      "Use patterns only where they simplify change and testing.",
    ];
  }
  return [
    "Answer with a concrete situation and your personal contribution.",
    "Use measurable outcomes where you have verified evidence.",
    "Explain trade-offs, learning, and what you would do differently.",
  ];
}

function QuestionPractice({
  question,
  progress,
}: {
  question: InterviewQuestion;
  progress?: InterviewProgress["by_question"][string];
}) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"description" | "solution" | "discussion" | "submissions" | "coach">("description");
  const [answer, setAnswer] = useState("");
  const [code, setCode] = useState('print("ApplyAI interview sandbox")');
  const [hintLevel, setHintLevel] = useState(0);
  const [hint, setHint] = useState<string | null>(null);
  const [result, setResult] = useState<{ score: number; feedback: Record<string, unknown> } | null>(null);
  const [discussionDraft, setDiscussionDraft] = useState({ title: "", body: "" });

  const submissions = useQuery({
    queryKey: ["interview-intelligence-submissions", question.slug],
    queryFn: ({ signal }) => interviewIntelligenceApi.submissions(question.slug, signal),
  });
  const discussion = useQuery({
    queryKey: ["interview-intelligence-community", "question", question.id],
    queryFn: ({ signal }) => interviewIntelligenceApi.community(question.id, signal),
  });

  const coach = useMutation({
    mutationFn: () => interviewIntelligenceApi.coach(question.id, answer, hintLevel),
    onSuccess: (data) => {
      setHint(data.hint);
      setHintLevel(data.next_level);
    },
  });
  const attempt = useMutation({
    mutationFn: () => interviewIntelligenceApi.attempt({
      question_id: question.id,
      answer_text: answer.trim() || null,
      code_text: question.track === "CODING" ? (code.trim() || null) : null,
    }),
    onSuccess: async (data) => {
      setResult({ score: data.score, feedback: data.feedback });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["interview-intelligence-progress"] }),
        queryClient.invalidateQueries({ queryKey: ["interview-intelligence-submissions", question.slug] }),
      ]);
      toast.success("Practice attempt saved");
    },
  });
  const createDiscussion = useMutation({
    mutationFn: () => interviewIntelligenceApi.createCommunity({
      question_id: question.id,
      company: question.companies[0] ?? null,
      category: "INTERVIEW_EXPERIENCE",
      title: discussionDraft.title,
      body: discussionDraft.body,
    }),
    onSuccess: async () => {
      setDiscussionDraft({ title: "", body: "" });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["interview-intelligence-community"] }),
        queryClient.invalidateQueries({ queryKey: ["interview-intelligence-community", "question", question.id] }),
      ]);
      toast.success("Question discussion published");
    },
  });

  const tabs = [
    ["description", "Description"],
    ["solution", "Solution"],
    ["discussion", "Discussion"],
    ["submissions", "Submissions"],
    ["coach", "Coach"],
  ] as const;

  return <Card className="detail-section">
    <div className="section-header">
      <div>
        <p className="eyebrow">{question.track.replaceAll("_", " ")} · {question.difficulty}</p>
        <h2>{question.title}</h2>
        <p>{question.summary}</p>
      </div>
      <div className="button-row">
        <Badge tone="info">Frequency {question.frequency_score}</Badge>
        <Badge tone={question.confidence >= 70 ? "success" : "neutral"}>Confidence {question.confidence}%</Badge>
      </div>
    </div>

    <div className="button-row">
      {question.stages.map((stage) => <Badge key={stage}>{stage}</Badge>)}
      {question.companies.map((company) => <Badge key={company} tone="info">{company}</Badge>)}
      <Badge tone="neutral">{recencyLabel(question.last_reported_at)}</Badge>
      {progress?.attempts ? <Badge tone={scoreTone(progress.best_score ?? 0)}>
        Practiced {progress.attempts}× · best {progress.best_score ?? 0}%
      </Badge> : null}
    </div>

    <div className="button-row" role="tablist" aria-label="Question workspace">
      {tabs.map(([value, label]) => <button
        key={value}
        type="button"
        role="tab"
        aria-selected={activeTab === value}
        onClick={() => setActiveTab(value)}
        style={{
          border: "1px solid var(--border)",
          borderRadius: 999,
          padding: "8px 12px",
          background: activeTab === value ? "var(--surface-raised)" : "transparent",
          color: "inherit",
          cursor: "pointer",
          fontWeight: activeTab === value ? 700 : 500,
        }}
      >
        {label}
      </button>)}
    </div>

    {activeTab === "description" ? <>
      <p style={{ fontSize: 18 }}><strong>{question.prompt}</strong></p>

      {question.skills.length || question.patterns.length ? <Card>
        <p className="eyebrow">What this tests</p>
        {question.skills.length ? <p>{question.skills.join(" · ")}</p> : null}
        {question.patterns.length ? <p className="muted">Common patterns: {question.patterns.join(" · ")}</p> : null}
      </Card> : null}

      <Card>
        <p className="eyebrow">Interview evaluation checklist</p>
        <ul>{questionGuidance(question.track).map((item) => <li key={item}>{item}</li>)}</ul>
      </Card>

      {question.track === "CODING" ? <InterviewCodeRunner code={code} onCodeChange={setCode} /> : null}

      <Field label="Your answer" htmlFor={`answer-${question.id}`}>
        <Textarea
          id={`answer-${question.id}`}
          rows={9}
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
        />
      </Field>
      <Button onClick={() => attempt.mutate()} disabled={(!answer.trim() && !(question.track === "CODING" && code.trim())) || attempt.isPending}>
        <Target size={15}/>Score and save submission
      </Button>

      {result ? <Card style={{ marginTop: 14 }}>
        <div className="section-header">
          <h3>Practice result</h3>
          <Badge tone={scoreTone(result.score)}>{result.score}%</Badge>
        </div>
        <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{JSON.stringify(result.feedback, null, 2)}</pre>
      </Card> : null}
    </> : null}

    {activeTab === "solution" ? <>
      <Card>
        <p className="eyebrow">Clean-room solution framework</p>
        <p className="muted">This outline is authored inside ApplyAI. It does not reproduce third-party solutions.</p>
        {question.solution_outline.length ? <ol>{question.solution_outline.map((item) => <li key={item}>{item}</li>)}</ol> : <p>No solution outline has been authored for this prompt yet.</p>}
      </Card>
      {question.follow_ups.length ? <Card>
        <p className="eyebrow">Interviewer follow-ups</p>
        <ol>{question.follow_ups.map((item) => <li key={item}>{item}</li>)}</ol>
      </Card> : null}
    </> : null}

    {activeTab === "discussion" ? <>
      <p className="muted">Question discussion is candidate community content and never changes canonical question evidence.</p>
      <Field label="Discussion title" htmlFor={`discussion-title-${question.id}`}>
        <input
          id={`discussion-title-${question.id}`}
          value={discussionDraft.title}
          onChange={(event) => setDiscussionDraft((value) => ({ ...value, title: event.target.value }))}
        />
      </Field>
      <Field label="Post" htmlFor={`discussion-body-${question.id}`}>
        <Textarea
          id={`discussion-body-${question.id}`}
          rows={5}
          value={discussionDraft.body}
          onChange={(event) => setDiscussionDraft((value) => ({ ...value, body: event.target.value }))}
        />
      </Field>
      <Button
        onClick={() => createDiscussion.mutate()}
        disabled={discussionDraft.title.trim().length < 5 || discussionDraft.body.trim().length < 20 || createDiscussion.isPending}
      >
        <MessageSquareText size={15}/>Publish discussion
      </Button>
      <div className="list-stack" style={{ marginTop: 18 }}>
        {(discussion.data ?? []).map((item: InterviewCommunityPost) => <div key={item.id} style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}>
          <strong>{item.title}</strong>
          <p className="muted">{item.reaction_count} reactions · {item.replies.length} replies · {new Date(item.created_at).toLocaleString()}</p>
          <p>{item.body}</p>
        </div>)}
        {!discussion.isLoading && !(discussion.data ?? []).length ? <EmptyState title="No discussion yet" description="Start a question-specific discussion without altering the evidence-backed question bank." /> : null}
      </div>
    </> : null}

    {activeTab === "submissions" ? <>
      {submissions.isLoading ? <Skeleton className="page-skeleton" /> : <>
        <div className="dashboard-grid">
          <Card><p className="eyebrow">Your submissions</p><h3>{submissions.data?.total ?? 0}</h3></Card>
          <Card><p className="eyebrow">Average score</p><h3>{submissions.data?.average_score ?? "—"}</h3></Card>
          <Card><p className="eyebrow">Strong attempts</p><h3>{submissions.data?.strong_attempts ?? 0}</h3><p className="muted">Score 80% or higher</p></Card>
        </div>
        <div className="list-stack">
          {(submissions.data?.items ?? []).map((item) => <Card key={item.id}>
            <div className="section-header">
              <div>
                <strong>{new Date(item.created_at).toLocaleString()}</strong>
                <p className="muted">{item.status}</p>
              </div>
              {item.score != null ? <Badge tone={scoreTone(item.score)}>{item.score}%</Badge> : <Badge>Unscored</Badge>}
            </div>
            {item.answer_excerpt ? <p>{item.answer_excerpt}</p> : <p className="muted">No text answer stored for this attempt.</p>}
          </Card>)}
          {!submissions.data?.items.length ? <EmptyState title="No submissions yet" description="Score your first answer from the Description tab and it will appear here." /> : null}
        </div>
      </>}
    </> : null}

    {activeTab === "coach" ? <>
      <p className="muted">ApplyAI coaching uses staged hints from clean-room question metadata. It does not reveal or copy third-party solutions.</p>
      <Field label="Your current thinking" htmlFor={`coach-answer-${question.id}`}>
        <Textarea
          id={`coach-answer-${question.id}`}
          rows={7}
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
        />
      </Field>
      <Button variant="secondary" onClick={() => coach.mutate()} disabled={coach.isPending}>
        <Sparkles size={15}/>Get next staged hint
      </Button>
      {hint ? <Card style={{ marginTop: 14 }}>
        <p className="eyebrow">Progressive hint {hintLevel}</p>
        <p>{hint}</p>
      </Card> : null}
    </> : null}
  </Card>;
}

export function InterviewIntelligenceHub() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({
    q: "",
    company: "",
    track: "",
    difficulty: "",
    stage: "",
    freshness: "",
    sort: "frequency",
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState({ company: "", role: "", interview_stage: "", title: "", body: "" });
  const [community, setCommunity] = useState({ company: "", title: "", body: "" });

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.q.trim()) params.set("q", filters.q.trim());
    if (filters.company) params.set("company", filters.company);
    if (filters.track) params.set("track", filters.track);
    if (filters.difficulty) params.set("difficulty", filters.difficulty);
    if (filters.stage) params.set("stage", filters.stage);
    if (filters.freshness) params.set("reported_within_days", filters.freshness);
    params.set("sort", filters.sort);
    return params.toString();
  }, [filters]);

  const questions = useQuery({
    queryKey: ["interview-intelligence-questions", queryString],
    queryFn: ({ signal }) => interviewIntelligenceApi.questions(queryString, signal),
  });
  const companies = useQuery({
    queryKey: ["interview-intelligence-companies"],
    queryFn: ({ signal }) => interviewIntelligenceApi.companies(signal),
  });
  const progress = useQuery({
    queryKey: ["interview-intelligence-progress"],
    queryFn: ({ signal }) => interviewIntelligenceApi.progress(signal),
  });
  const communityFeed = useQuery({
    queryKey: ["interview-intelligence-community"],
    queryFn: ({ signal }) => interviewIntelligenceApi.community(undefined, signal),
  });

  const availableStages = useMemo(() => {
    const stages = new Set<string>();
    for (const company of companies.data ?? []) {
      Object.keys(company.stages ?? {}).forEach((stage) => stages.add(stage));
    }
    for (const question of questions.data?.items ?? []) {
      question.stages.forEach((stage) => stages.add(stage));
    }
    return [...stages].sort();
  }, [companies.data, questions.data]);

  const selected = useMemo(
    () => questions.data?.items.find((item) => item.id === selectedId) ?? questions.data?.items[0] ?? null,
    [questions.data, selectedId],
  );

  const submitReport = useMutation({
    mutationFn: () => interviewIntelligenceApi.submitReport({
      ...report,
      company: report.company || null,
      role: report.role || null,
      interview_stage: report.interview_stage || null,
      title: report.title || null,
    }),
    onSuccess: () => {
      setReport({ company: "", role: "", interview_stage: "", title: "", body: "" });
      toast.success("Interview report submitted for moderation");
    },
  });
  const createCommunity = useMutation({
    mutationFn: () => interviewIntelligenceApi.createCommunity({
      ...community,
      company: community.company || null,
      category: "INTERVIEW_EXPERIENCE",
    }),
    onSuccess: async () => {
      setCommunity({ company: "", title: "", body: "" });
      await queryClient.invalidateQueries({ queryKey: ["interview-intelligence-community"] });
      toast.success("Community post published");
    },
  });

  if (questions.isLoading || companies.isLoading || progress.isLoading) return <Skeleton className="page-skeleton" />;

  return <div className="page-stack">
    <PageHeader
      eyebrow="ApplyAI Prepare"
      title="Company Question Bank + Interview Intelligence"
      description="Practice clean-room interview questions by company, round, track, difficulty and freshness. Company-specific claims only appear after approved evidence is linked; proprietary question banks are never copied."
    />

    <div className="dashboard-grid">
      <Card><p className="eyebrow">Question bank</p><h2>{questions.data?.total ?? 0}</h2><p>Current filtered clean-room prompts</p></Card>
      <Card><p className="eyebrow">Practice attempts</p><h2>{progress.data?.total_attempts ?? 0}</h2><p>Durable across sessions</p></Card>
      <Card><p className="eyebrow">Company collections</p><h2>{companies.data?.length ?? 0}</h2><p>Only evidence-backed company labels</p></Card>
    </div>

    <Card className="detail-section">
      <div className="section-header">
        <div>
          <h2><Search size={18} style={{ verticalAlign: "middle", marginRight: 7 }}/>Find interview questions</h2>
          <p>Filter the bank the way you prepare for a real company loop.</p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setFilters({ q: "", company: "", track: "", difficulty: "", stage: "", freshness: "", sort: "frequency" })}
        >
          Reset filters
        </Button>
      </div>

      <div className="dashboard-grid">
        <Field label="Search" htmlFor="question-search">
          <input
            id="question-search"
            value={filters.q}
            placeholder="Search title, summary or prompt"
            onChange={(event) => setFilters((value) => ({ ...value, q: event.target.value }))}
          />
        </Field>
        <Field label="Company" htmlFor="question-company">
          <NativeSelect
            id="question-company"
            value={filters.company}
            onChange={(event) => setFilters((value) => ({ ...value, company: event.target.value }))}
          >
            <option value="">All evidence-backed companies</option>
            {(companies.data ?? []).map((item) => <option key={item.slug} value={item.name}>{item.name}</option>)}
          </NativeSelect>
        </Field>
        <Field label="Track" htmlFor="question-track">
          <NativeSelect
            id="question-track"
            value={filters.track}
            onChange={(event) => setFilters((value) => ({ ...value, track: event.target.value }))}
          >
            {TRACKS.map((item) => <option key={item || "all"} value={item}>{item ? item.replaceAll("_", " ") : "All tracks"}</option>)}
          </NativeSelect>
        </Field>
        <Field label="Difficulty" htmlFor="question-difficulty">
          <NativeSelect
            id="question-difficulty"
            value={filters.difficulty}
            onChange={(event) => setFilters((value) => ({ ...value, difficulty: event.target.value }))}
          >
            {DIFFICULTIES.map((item) => <option key={item || "all"} value={item}>{item || "All difficulties"}</option>)}
          </NativeSelect>
        </Field>
        <Field label="Interview stage" htmlFor="question-stage">
          <NativeSelect
            id="question-stage"
            value={filters.stage}
            onChange={(event) => setFilters((value) => ({ ...value, stage: event.target.value }))}
          >
            <option value="">All stages</option>
            {availableStages.map((item) => <option key={item} value={item}>{item}</option>)}
          </NativeSelect>
        </Field>
        <Field label="Freshness" htmlFor="question-freshness">
          <NativeSelect
            id="question-freshness"
            value={filters.freshness}
            onChange={(event) => setFilters((value) => ({ ...value, freshness: event.target.value }))}
          >
            <option value="">Any evidence age</option>
            <option value="30">Reported within 30 days</option>
            <option value="90">Reported within 90 days</option>
            <option value="180">Reported within 180 days</option>
          </NativeSelect>
        </Field>
        <Field label="Sort" htmlFor="question-sort">
          <NativeSelect
            id="question-sort"
            value={filters.sort}
            onChange={(event) => setFilters((value) => ({ ...value, sort: event.target.value }))}
          >
            <option value="frequency">Most frequent</option>
            <option value="recent">Most recently reported</option>
            <option value="confidence">Highest confidence</option>
          </NativeSelect>
        </Field>
      </div>
    </Card>

    <div className="detail-grid">
      <div className="detail-main">
        <Card className="detail-section">
          <div className="section-header">
            <div>
              <h2>Question intelligence</h2>
              <p>Frequency, freshness and company labels are provenance-aware rather than copied from third-party banks.</p>
            </div>
            <Badge tone="info">{questions.data?.total ?? 0} matches</Badge>
          </div>
          <div className="list-stack">
            {questions.data?.items.map((item) => {
              const itemProgress = progress.data?.by_question?.[item.id];
              return <button
                key={item.id}
                type="button"
                onClick={() => setSelectedId(item.id)}
                style={{
                  textAlign: "left",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: 14,
                  background: selected?.id === item.id ? "var(--surface-raised)" : "transparent",
                  color: "inherit",
                  cursor: "pointer",
                }}
              >
                <div className="section-header">
                  <strong>{item.title}</strong>
                  <div className="button-row">
                    <Badge>{item.difficulty}</Badge>
                    {itemProgress?.attempts ? <Badge tone={scoreTone(itemProgress.best_score ?? 0)}>
                      best {itemProgress.best_score ?? 0}%
                    </Badge> : null}
                  </div>
                </div>
                <p className="muted">
                  {item.track.replaceAll("_", " ")} · frequency {item.frequency_score} · confidence {item.confidence}% · {recencyLabel(item.last_reported_at)}
                </p>
                <div className="button-row">
                  {item.stages.slice(0, 3).map((stage) => <Badge key={stage}>{stage}</Badge>)}
                  {item.companies.slice(0, 3).map((company) => <Badge key={company} tone="info">{company}</Badge>)}
                </div>
              </button>;
            })}
            {!questions.data?.items.length ? <EmptyState
              title="No questions match"
              description="Try a broader filter. Company-specific results appear only when approved evidence supports the company label."
            /> : null}
          </div>
        </Card>

        {selected ? <QuestionPractice key={selected.id} question={selected} progress={progress.data?.by_question?.[selected.id]} /> : null}

        <Card className="detail-section">
          <div className="section-header">
            <div>
              <h2>Candidate interview reports</h2>
              <p>Submit firsthand interview experience. Reports are fingerprinted and require operator moderation before influencing question evidence.</p>
            </div>
            <Send size={20}/>
          </div>
          <div className="dashboard-grid">
            <Field label="Company" htmlFor="report-company"><input id="report-company" value={report.company} onChange={(event) => setReport((value) => ({ ...value, company: event.target.value }))} /></Field>
            <Field label="Role" htmlFor="report-role"><input id="report-role" value={report.role} onChange={(event) => setReport((value) => ({ ...value, role: event.target.value }))} /></Field>
            <Field label="Interview stage" htmlFor="report-stage"><input id="report-stage" value={report.interview_stage} onChange={(event) => setReport((value) => ({ ...value, interview_stage: event.target.value }))} /></Field>
          </div>
          <Field label="Title" htmlFor="report-title"><input id="report-title" value={report.title} onChange={(event) => setReport((value) => ({ ...value, title: event.target.value }))} /></Field>
          <Field label="What happened?" htmlFor="report-body"><Textarea id="report-body" rows={7} value={report.body} onChange={(event) => setReport((value) => ({ ...value, body: event.target.value }))} /></Field>
          <Button onClick={() => submitReport.mutate()} disabled={report.body.trim().length < 20 || submitReport.isPending}>Submit for moderation</Button>
        </Card>

        <Card className="detail-section">
          <div className="section-header">
            <div><h2>Candidate community</h2><p>Share interview experience without changing canonical question evidence.</p></div>
            <MessageSquareText size={20}/>
          </div>
          <Field label="Company (optional)" htmlFor="community-company"><input id="community-company" value={community.company} onChange={(event) => setCommunity((value) => ({ ...value, company: event.target.value }))} /></Field>
          <Field label="Title" htmlFor="community-title"><input id="community-title" value={community.title} onChange={(event) => setCommunity((value) => ({ ...value, title: event.target.value }))} /></Field>
          <Field label="Post" htmlFor="community-body"><Textarea id="community-body" rows={5} value={community.body} onChange={(event) => setCommunity((value) => ({ ...value, body: event.target.value }))} /></Field>
          <Button onClick={() => createCommunity.mutate()} disabled={community.title.trim().length < 5 || community.body.trim().length < 20 || createCommunity.isPending}>Publish post</Button>
          <div className="list-stack" style={{ marginTop: 18 }}>
            {(communityFeed.data ?? []).map((item) => <div key={item.id} style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              <strong>{item.title}</strong>
              <p className="muted">{item.company || "General"} · {item.reaction_count} reactions</p>
              <p>{item.body}</p>
            </div>)}
          </div>
        </Card>
      </div>

      <aside className="detail-aside">
        <Card className="sticky-actions">
          <h2><Building2 size={18} style={{ verticalAlign: "middle", marginRight: 7 }}/>Company collections</h2>
          {(companies.data ?? []).length ? <div className="list-stack">
            {companies.data?.slice(0, 20).map((item) => <button
              key={item.slug}
              type="button"
              onClick={() => setFilters((value) => ({ ...value, company: item.name }))}
              style={{ textAlign: "left", border: 0, padding: 0, background: "transparent", color: "inherit", cursor: "pointer" }}
            >
              <strong>{item.name}</strong>
              <p className="muted">{item.question_count} questions · {item.report_count} linked reports</p>
            </button>)}
          </div> : <p className="muted">
            Company-specific evidence appears only after approved candidate reports are linked by an operator. The seeded clean-room bank intentionally makes no unsupported company-specific claims.
          </p>}

          <h3>Track progress</h3>
          {Object.entries(progress.data?.by_track ?? {}).map(([name, stats]) => <div key={name} className="section-header">
            <span>{name.replaceAll("_", " ")}</span>
            <Badge tone={scoreTone(stats.average_score)}>{stats.average_score}% · {stats.attempts}</Badge>
          </div>)}
        </Card>
      </aside>
    </div>
  </div>;
}
