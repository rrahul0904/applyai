"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, BrainCircuit, CheckCircle2, Headphones, RefreshCw, Save, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, Field, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { interviewIntelligenceApi, type InterviewLifecyclePhase, type InterviewWorkspace } from "@/lib/api/interview-intelligence-client";

function tone(score: number) {
  if (score >= 80) return "success" as const;
  if (score >= 60) return "info" as const;
  return "warning" as const;
}

function speak(lines: { speaker: string; text: string }[]) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const text = lines.map((line) => `${line.speaker}. ${line.text}`).join(" ");
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

function PhasePanel({ jobId, workspace, phase }: { jobId: string; workspace: InterviewWorkspace; phase: InterviewLifecyclePhase }) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState(phase.notes ?? "");
  const [reflection, setReflection] = useState({ how_it_went: "", surprise: "", prepare_differently: "" });
  const save = useMutation({
    mutationFn: () => interviewIntelligenceApi.notes(jobId, phase.phase_number, notes),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["interview-intelligence-workspace", jobId] });
      toast.success("Private phase notes saved");
    },
  });
  const reflect = useMutation({
    mutationFn: () => interviewIntelligenceApi.reflect(jobId, phase.phase_number, { ...reflection, difficult_questions: [], learned_about_team: null }),
    onSuccess: async () => {
      setReflection({ how_it_went: "", surprise: "", prepare_differently: "" });
      await queryClient.invalidateQueries({ queryKey: ["interview-intelligence-workspace", jobId] });
      toast.success("Reflection saved and next phase unlocked");
    },
  });
  const current = workspace.current_phase_number === phase.phase_number;
  const complete = workspace.current_phase_number > phase.phase_number || (workspace.status === "COMPLETE" && phase.phase_number === 4);
  return <div className="detail-grid">
    <div className="detail-main">
      <Card className="detail-section">
        <div className="section-header"><div><p className="eyebrow">Phase {phase.phase_number} · {phase.phase_type.replaceAll("_", " ")}</p><h2>{phase.title}</h2></div><Badge tone={complete ? "success" : current ? "info" : "neutral"}>{complete ? "Complete" : current ? "Current" : "Upcoming"}</Badge></div>
        <div className="list-stack">{(phase.prep.focus ?? []).map((item) => <div key={item} style={{ display: "flex", gap: 9 }}><CheckCircle2 size={16} style={{ marginTop: 3 }} /><span>{item}</span></div>)}</div>
      </Card>
      <Card className="detail-section"><h2>Round questions</h2><div className="list-stack">{phase.questions.map((question) => <div key={question.order} style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}><strong>{question.order}. {question.prompt}</strong><p className="muted">{question.evidence_guidance}</p></div>)}</div></Card>
      <Card className="detail-section"><h2>Flashcards</h2><div className="dashboard-grid">{phase.flashcards.map((card) => <Card key={card.front}><p className="eyebrow">{card.front}</p><p>{card.back}</p></Card>)}</div></Card>
      <Card className="detail-section"><h2>Private notes</h2><Field label="What should you remember for this round?" htmlFor={`phase-notes-${phase.phase_number}`}><Textarea id={`phase-notes-${phase.phase_number}`} rows={6} value={notes} onChange={(event) => setNotes(event.target.value)} /></Field><Button variant="secondary" onClick={() => save.mutate()} disabled={save.isPending}><Save size={15}/>Save notes</Button></Card>
      <Card className="detail-section"><h2>Post-round retrospective</h2><p className="muted">Only the current phase can advance the lifecycle. Previous rounds stay editable as notes, not as progression controls.</p><Field label="How did it go?" htmlFor={`how-${phase.phase_number}`}><Textarea id={`how-${phase.phase_number}`} rows={3} value={reflection.how_it_went} onChange={(event) => setReflection((value) => ({ ...value, how_it_went: event.target.value }))} /></Field><Field label="What surprised you?" htmlFor={`surprise-${phase.phase_number}`}><Textarea id={`surprise-${phase.phase_number}`} rows={3} value={reflection.surprise} onChange={(event) => setReflection((value) => ({ ...value, surprise: event.target.value }))} /></Field><Field label="What will you prepare differently next round?" htmlFor={`different-${phase.phase_number}`}><Textarea id={`different-${phase.phase_number}`} rows={3} value={reflection.prepare_differently} onChange={(event) => setReflection((value) => ({ ...value, prepare_differently: event.target.value }))} /></Field><Button onClick={() => reflect.mutate()} disabled={!current || reflect.isPending || !reflection.how_it_went.trim()}><BookOpenCheck size={15}/>{complete ? "Round already completed" : current ? "Complete this round" : "Complete current round first"}</Button></Card>
    </div>
    <aside className="detail-aside"><Card className="sticky-actions"><h2>Cheat sheet</h2><pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", margin: 0 }}>{JSON.stringify(phase.cheat_sheet, null, 2)}</pre>{phase.carry_forward.length ? <><h3>Carry forward</h3><div className="list-stack">{phase.carry_forward.map((item) => <p key={item}>{item}</p>)}</div></> : null}</Card></aside>
  </div>;
}

export function InterviewIntelligenceLifecycle({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [selectedPhase, setSelectedPhase] = useState<number | null>(null);
  const workspace = useQuery({ queryKey: ["interview-intelligence-workspace", jobId], queryFn: ({ signal }) => interviewIntelligenceApi.workspace(jobId, signal), retry: false });
  const bootstrap = useMutation({
    mutationFn: () => interviewIntelligenceApi.bootstrap(jobId, {}),
    onSuccess: async (data) => {
      setSelectedPhase(data.current_phase_number);
      await queryClient.invalidateQueries({ queryKey: ["interview-intelligence-workspace", jobId] });
      toast.success("Interview intelligence workspace is ready");
    },
  });
  const refresh = useMutation({
    mutationFn: () => interviewIntelligenceApi.bootstrap(jobId, { regenerate: true }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["interview-intelligence-workspace", jobId] });
      toast.success("Preparation refreshed without losing notes or carry-forward actions");
    },
  });
  const data = workspace.data;
  const phase = useMemo(() => {
    if (!data) return null;
    const target = selectedPhase ?? data.current_phase_number;
    return data.lifecycle.phases.find((item) => item.phase_number === target) ?? data.lifecycle.phases[0] ?? null;
  }, [data, selectedPhase]);
  if (workspace.isLoading) return <Skeleton className="page-skeleton" />;
  if (!data) return <Card className="detail-section"><div className="section-header"><div><p className="eyebrow">Reverse-engineered interview lifecycle</p><h2>Build interview intelligence</h2><p>Layer company/role context, four interview rounds, flashcards, retrospectives, podcast scripts and a STAR story workflow over the existing ApplyAI Prepare stack.</p></div><Button onClick={() => bootstrap.mutate()} disabled={bootstrap.isPending}><Sparkles size={16}/>Build workspace</Button></div></Card>;
  return <section style={{ marginTop: 28 }}>
    <PageHeader eyebrow="Interview intelligence" title={`${data.lifecycle.company} · ${data.lifecycle.job_title}`} description="Evidence-grounded lifecycle intelligence layered on top of ApplyAI Prepare." actions={<Button variant="secondary" onClick={() => refresh.mutate()} disabled={refresh.isPending}><RefreshCw size={15}/>Refresh context</Button>} />
    <div className="dashboard-grid"><Card><p className="eyebrow">Readiness</p><h2>{data.readiness.score}%</h2><Badge tone={tone(data.readiness.score)}>{data.readiness.band}</Badge></Card><Card><p className="eyebrow">Current round</p><h2>{data.current_phase_number}/4</h2><p>{data.lifecycle.phases.find((item) => item.phase_number === data.current_phase_number)?.title ?? "Complete"}</p></Card><Card><p className="eyebrow">Evidence gaps</p><h2>{data.lifecycle.gaps.length}</h2><p>{data.lifecycle.gaps.slice(0, 3).join(" · ") || "No leading gaps detected"}</p></Card></div>
    <div className="button-row" style={{ margin: "20px 0" }}>{data.lifecycle.phases.map((item) => <Button key={item.phase_number} size="small" variant={(selectedPhase ?? data.current_phase_number) === item.phase_number ? "secondary" : "ghost"} onClick={() => setSelectedPhase(item.phase_number)}>Round {item.phase_number}: {item.title}</Button>)}</div>
    {phase ? <PhasePanel key={phase.phase_number} jobId={jobId} workspace={data} phase={phase} /> : null}
    <Card className="detail-section"><div className="section-header"><div><p className="eyebrow">Audio-friendly prep</p><h2>Podcast briefings</h2><p>Five generated scripts use browser speech synthesis. No fake hosted audio or broken RSS feed is exposed.</p></div><Headphones size={22}/></div><div className="dashboard-grid">{data.podcasts.map((episode) => <Card key={episode.episode_number}><p className="eyebrow">Episode {episode.episode_number}</p><h3>{episode.title}</h3><p>{episode.summary}</p><Button size="small" variant="secondary" onClick={() => speak(episode.script)}><Headphones size={14}/>Listen</Button></Card>)}</div></Card>
    {data.lifecycle.carry_forward.length ? <Card className="detail-section"><h2><BrainCircuit size={18} style={{ verticalAlign: "middle", marginRight: 7 }}/>Carry-forward actions</h2><div className="list-stack">{data.lifecycle.carry_forward.map((item) => <p key={item}>• {item}</p>)}</div></Card> : null}
  </section>;
}
