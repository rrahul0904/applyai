"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen, Brain, Building2, CheckCircle2, Clipboard, Headphones, Mic, Pause,
  Play, RefreshCw, Rss, Sparkles, Target, UserRoundSearch, Volume2,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Badge, Button, Card, ErrorState, Field, Input, NativeSelect, PageHeader, Progress,
  Skeleton, Tabs, TabsContent, TabsList, TabsTrigger, Textarea,
} from "@/components/ui";
import {
  PlatformApiError, platformApi, type InterviewAttemptResult, type InterviewPhase,
  type InterviewPreparation, type InterviewQuestion, type PodcastEpisode,
} from "@/lib/api/platform-client";

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function metric(value: unknown, fallback = "—") {
  return typeof value === "number" || typeof value === "string" ? String(value) : fallback;
}

function useSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  function stopSpeaking() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  function speakSegments(segments: Array<{ speaker: string; text: string }>) {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      toast.error("Audio playback is not available in this browser.");
      return;
    }
    stopSpeaking();
    const voices = window.speechSynthesis.getVoices();
    segments.forEach((segment, index) => {
      const utterance = new SpeechSynthesisUtterance(segment.text);
      utterance.rate = 0.98;
      utterance.pitch = index % 2 === 0 ? 0.95 : 1.05;
      if (voices.length) utterance.voice = voices[index % Math.min(voices.length, 4)] ?? voices[0];
      if (index === segments.length - 1) utterance.onend = () => setSpeaking(false);
      window.speechSynthesis.speak(utterance);
    });
    setSpeaking(true);
  }

  function startDictation(onText: (text: string) => void) {
    if (typeof window === "undefined") return;
    const speechWindow = window as unknown as {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Constructor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Constructor) {
      toast.error("Voice transcription is unavailable here. You can still type your answer.");
      return;
    }
    const recognition = new Constructor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    let finalText = "";
    recognition.onresult = (event) => {
      let interim = "";
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (!result) continue;
        if (result.isFinal) finalText += `${result[0]?.transcript ?? ""} `;
        else interim += result[0]?.transcript ?? "";
      }
      onText(`${finalText}${interim}`.trim());
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }

  function stopDictation() {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setListening(false);
  }

  return { speaking, listening, speakSegments, stopSpeaking, startDictation, stopDictation };
}

function SetupCard({ jobId, initial }: { jobId: string; initial?: InterviewPreparation | null }) {
  const queryClient = useQueryClient();
  const [country, setCountry] = useState(initial?.country ?? "United States");
  const [date, setDate] = useState(initial?.interview_date?.slice(0, 16) ?? "");
  const [phase, setPhase] = useState(String(initial?.current_phase_number ?? 1));
  const [name, setName] = useState(initial?.interviewer.name ?? "");
  const [title, setTitle] = useState(initial?.interviewer.title ?? "");
  const [url, setUrl] = useState(initial?.interviewer.url ?? "");
  const bootstrap = useMutation({
    mutationFn: (regenerate = false) => platformApi.interviewIntelligence.bootstrap(jobId, {
      country: country || null,
      interview_date: date ? new Date(date).toISOString() : null,
      current_phase_number: Number(phase),
      interviewer_name: name || null,
      interviewer_title: title || null,
      interviewer_url: url || null,
      regenerate,
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["interview-intelligence", jobId] });
      toast.success(initial ? "Interview setup updated" : "Interview workspace created");
    },
  });
  return <Card className="detail-section">
    <div className="section-header"><div><h2>{initial ? "Interview setup" : "Create your interview command center"}</h2><p>Ground preparation in this job, your verified Career Memory, the interview round, and interviewer context.</p></div><Badge tone="info">Evidence locked</Badge></div>
    <div className="form-grid">
      <Field label="Country" htmlFor="interview-country"><Input id="interview-country" value={country} onChange={(event) => setCountry(event.target.value)} /></Field>
      <Field label="Interview date" htmlFor="interview-date"><Input id="interview-date" type="datetime-local" value={date} onChange={(event) => setDate(event.target.value)} /></Field>
      <Field label="Current round" htmlFor="interview-phase"><NativeSelect id="interview-phase" value={phase} onChange={(event) => setPhase(event.target.value)}><option value="1">Recruiter screen</option><option value="2">Hiring manager</option><option value="3">Technical / case panel</option><option value="4">Executive / culture</option></NativeSelect></Field>
      <Field label="Interviewer name" htmlFor="interviewer-name"><Input id="interviewer-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Optional" /></Field>
      <Field label="Interviewer title" htmlFor="interviewer-title"><Input id="interviewer-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Optional" /></Field>
      <Field label="Public profile URL" htmlFor="interviewer-url"><Input id="interviewer-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://..." /></Field>
    </div>
    <div className="button-row" style={{ marginTop: 18 }}><Button onClick={() => bootstrap.mutate(false)} disabled={bootstrap.isPending}><Sparkles size={16}/>{initial ? "Save setup" : "Build interview prep"}</Button>{initial ? <Button variant="secondary" onClick={() => bootstrap.mutate(true)} disabled={bootstrap.isPending}><RefreshCw size={16}/>Refresh generated prep</Button> : null}</div>
  </Card>;
}

function ReadinessCard({ prep }: { prep: InterviewPreparation }) {
  const readiness = prep.readiness ?? {};
  const overall = Number(readiness.overall ?? 45);
  const dimensions = [
    ["Practice", Number(readiness.practice ?? 45)],
    ["Round learning", Number(readiness.round_learning ?? 0)],
    ["Notes captured", Number(readiness.notes ?? 0)],
  ] as const;
  return <Card className="detail-section">
    <div className="section-header"><div><p className="eyebrow">Adaptive readiness</p><h2>{overall}% ready</h2></div><Badge tone={overall >= 80 ? "success" : overall >= 60 ? "info" : "warning"}>{Number(readiness.attempt_count ?? 0)} practice attempts</Badge></div>
    <Progress value={overall}/>
    <div style={{ display: "grid", gap: 14, marginTop: 20 }}>
      {dimensions.map(([label, value]) => <div key={label}><div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}><span>{label}</span><strong>{value}%</strong></div><Progress value={value}/></div>)}
    </div>
  </Card>;
}

function Overview({ prep }: { prep: InterviewPreparation }) {
  const company = asRecord(prep.company_research);
  const role = asRecord(prep.role_analysis);
  const resume = asRecord(prep.resume_analysis);
  const market = asRecord(prep.market_benchmark);
  const interviewer = asRecord(prep.interviewer.brief);
  const strengths = asStringArray(resume.matched_strengths);
  const gaps = asStringArray(resume.gaps_to_prepare);
  const focus = asStringArray(role.likely_focus);
  const priorities = asStringArray(interviewer.likely_priorities);
  return <div className="detail-grid">
    <div className="detail-main" style={{ display: "grid", gap: 18 }}>
      <Card className="detail-section"><div className="section-header"><div><h2>Role intelligence</h2><p>What this job is likely to test.</p></div><Target size={20}/></div><div className="button-row">{focus.map((item) => <Badge key={item} tone="info">{item}</Badge>)}</div><div style={{ marginTop: 18 }}><strong>Requirements</strong><ul>{asStringArray(role.requirements).slice(0, 8).map((item) => <li key={item}>{item}</li>)}</ul></div></Card>
      <Card className="detail-section"><div className="section-header"><div><h2>Candidate evidence map</h2><p>Strengths come from verified Career Memory; gaps remain explicit.</p></div><Brain size={20}/></div><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 18 }}><div><p className="eyebrow">Matched strengths</p>{strengths.length ? strengths.map((item) => <p key={item}>✓ {item}</p>) : <p className="muted">Add verified Career Memory evidence to improve personalization.</p>}</div><div><p className="eyebrow">Prepare transferability</p>{gaps.length ? gaps.map((item) => <p key={item}>→ {item}</p>) : <p className="muted">No obvious gaps found in the current evidence set.</p>}</div></div></Card>
      <Card className="detail-section"><div className="section-header"><div><h2>Market benchmark</h2><p>Current role-family demand from ApplyAI&apos;s active job corpus.</p></div><Building2 size={20}/></div><p><strong>{metric(market.comparison_job_count, "0")}</strong> comparable active jobs sampled.</p><div className="list-stack">{Array.isArray(market.skills) ? (market.skills as Array<Record<string, unknown>>).slice(0, 8).map((row) => <div key={String(row.skill)} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12 }}><span>{String(row.skill)}</span><Badge tone={row.candidate_evidence ? "success" : "warning"}>{metric(row.share_pct, "0")}% market · {row.candidate_evidence ? "evidence" : "gap"}</Badge></div>) : null}</div></Card>
    </div>
    <aside className="detail-aside" style={{ display: "grid", gap: 18, alignContent: "start" }}>
      <ReadinessCard prep={prep}/>
      <Card className="detail-section"><p className="eyebrow">Company briefing</p><h2>{metric(company.company_name, "Company")}</h2><p>{metric(company.description, "ApplyAI is using verified job-corpus signals for this baseline briefing.")}</p><p className="muted">{metric(company.evidence_basis, "Current ApplyAI evidence")}</p></Card>
      <Card className="detail-section"><p className="eyebrow">Interviewer brief</p><h2>{prep.interviewer.name || "Add an interviewer"}</h2><p>{prep.interviewer.title || "Title not supplied"}</p><div className="button-row">{priorities.slice(0, 5).map((item) => <Badge key={item}>{item}</Badge>)}</div><p className="muted" style={{ marginTop: 14 }}>{metric(interviewer.evidence_note, "ApplyAI will not invent interviewer-specific claims.")}</p></Card>
    </aside>
  </div>;
}

function Podcast({ prep }: { prep: InterviewPreparation }) {
  const speech = useSpeech();
  const [active, setActive] = useState<number | null>(null);
  function play(episode: PodcastEpisode) {
    setActive(episode.episode_number);
    speech.speakSegments(episode.script);
  }
  const feedUrl = typeof window === "undefined" ? platformApi.interviewIntelligence.feedPath(prep.private_feed_token) : `${window.location.origin}${platformApi.interviewIntelligence.feedPath(prep.private_feed_token)}`;
  return <div style={{ display: "grid", gap: 18 }}>
    <Card className="detail-section"><div className="section-header"><div><h2>Private prep feed</h2><p>Five job-specific episodes. Web playback uses browser speech synthesis, so the core experience has no TTS-vendor dependency. RSS automatically exposes hosted audio when an audio provider is configured.</p></div><Rss size={20}/></div><div className="button-row"><Button variant="secondary" onClick={() => { void navigator.clipboard?.writeText(feedUrl); toast.success("Private RSS feed copied"); }}><Clipboard size={16}/>Copy private RSS</Button>{speech.speaking ? <Button variant="ghost" onClick={speech.stopSpeaking}><Pause size={16}/>Stop playback</Button> : null}</div></Card>
    {prep.episodes.map((episode) => <Card className="detail-section" key={episode.id}><div className="section-header"><div><p className="eyebrow">Episode {episode.episode_number} · {episode.duration_estimate_minutes} min</p><h2>{episode.title}</h2></div><Button variant={active === episode.episode_number && speech.speaking ? "secondary" : "primary"} onClick={() => play(episode)}><Headphones size={16}/>{active === episode.episode_number && speech.speaking ? "Playing" : "Listen"}</Button></div><p>{episode.summary}</p><details><summary>Read transcript</summary><div style={{ display: "grid", gap: 12, marginTop: 14 }}>{episode.script.map((segment, index) => <div key={`${segment.speaker}-${index}`}><strong>{segment.speaker}</strong><p style={{ margin: "4px 0" }}>{segment.text}</p></div>)}</div></details></Card>)}
  </div>;
}

function QuizAndCards({ phase }: { phase: InterviewPhase }) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});
  return <div style={{ display: "grid", gap: 18 }}>
    <Card className="detail-section"><div className="section-header"><div><h2>Round quiz</h2><p>Eight checks calibrated to the preparation model.</p></div><Badge tone="info">{phase.quiz.length} questions</Badge></div>{phase.quiz.map((item, index) => <div key={item.id} style={{ borderTop: index ? "1px solid var(--line)" : undefined, padding: "18px 0" }}><strong>{index + 1}. {item.question}</strong><div style={{ display: "grid", gap: 8, marginTop: 10 }}>{item.options.map((option, optionIndex) => { const selected = answers[item.id] === optionIndex; const answered = answers[item.id] !== undefined; const correct = item.correct_index === optionIndex; return <button key={option} type="button" className="ui-button ui-button-secondary" style={{ justifyContent: "flex-start", minHeight: 40, background: answered && selected ? (correct ? "var(--sage)" : "#fff1d9") : undefined }} onClick={() => setAnswers((current) => ({ ...current, [item.id]: optionIndex }))}>{option}</button>; })}</div>{answers[item.id] !== undefined ? <p className="muted">{answers[item.id] === item.correct_index ? "Correct. " : "Review: "}{item.explanation}</p> : null}</div>)}</Card>
    <Card className="detail-section"><div className="section-header"><div><h2>Flashcards</h2><p>Four quick retrieval prompts for this round.</p></div><BookOpen size={20}/></div><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>{phase.flashcards.map((card, index) => <button key={`${card.front}-${index}`} type="button" className="ui-card" style={{ padding: 18, minHeight: 150, textAlign: "left", cursor: "pointer" }} onClick={() => setRevealed((current) => ({ ...current, [index]: !current[index] }))}><p className="eyebrow">{revealed[index] ? "Answer" : "Prompt"}</p><strong>{revealed[index] ? card.back : card.front}</strong><p className="muted">Click to {revealed[index] ? "hide" : "reveal"}</p></button>)}</div></Card>
  </div>;
}

function Rounds({ prep }: { prep: InterviewPreparation }) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState(prep.phases.find((item) => item.phase_number === prep.current_phase_number)?.id ?? prep.phases[0]?.id ?? "");
  const phase = prep.phases.find((item) => item.id === selectedId) ?? prep.phases[0];
  const [notes, setNotes] = useState(phase?.notes ?? "");
  const [went, setWent] = useState("");
  const [surprise, setSurprise] = useState("");
  const [difficult, setDifficult] = useState("");
  const [learned, setLearned] = useState("");
  const [different, setDifferent] = useState("");
  const saveNotes = useMutation({ mutationFn: () => phase ? platformApi.interviewIntelligence.saveNotes(phase.id, notes) : Promise.resolve(null), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["interview-intelligence", prep.job_id] }); toast.success("Round notes saved"); } });
  const reflect = useMutation({ mutationFn: () => phase ? platformApi.interviewIntelligence.saveReflection(phase.id, { how_it_went: went || null, surprise: surprise || null, difficult_questions: difficult.split("\n").map((item) => item.trim()).filter(Boolean), learned_about_team: learned || null, prepare_differently: different || null }) : Promise.resolve(null), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["interview-intelligence", prep.job_id] }); toast.success("Reflection saved and carried into the next round"); } });
  if (!phase) return null;
  const carryForward = asStringArray(phase.prep.carry_forward);
  return <div style={{ display: "grid", gap: 18 }}>
    <Card className="detail-section"><div className="button-row">{prep.phases.map((item) => <Button key={item.id} variant={item.id === phase.id ? "primary" : "secondary"} onClick={() => { setSelectedId(item.id); setNotes(item.notes ?? ""); }}>{item.phase_number}. {item.title} <Badge tone={item.status === "CURRENT" ? "success" : item.status === "COMPLETE" ? "info" : "neutral"}>{item.status}</Badge></Button>)}</div></Card>
    {carryForward.length ? <Card className="detail-section"><p className="eyebrow">From the previous round</p><h2>Adapt this round</h2>{carryForward.map((item) => <p key={item}>→ {item}</p>)}</Card> : null}
    <div className="detail-grid"><div className="detail-main" style={{ display: "grid", gap: 18 }}><Card className="detail-section"><div className="section-header"><div><h2>{phase.title} focus</h2><p>Targeted preparation for this stage.</p></div><Badge tone="info">Readiness {Number(phase.readiness?.score ?? 45)}%</Badge></div><div className="button-row">{asStringArray(phase.prep.focus).map((item) => <Badge key={item}>{item}</Badge>)}</div><ol>{asStringArray(phase.prep.target_questions).map((item) => <li key={item} style={{ marginBottom: 8 }}>{item}</li>)}</ol></Card><QuizAndCards phase={phase}/></div><aside className="detail-aside" style={{ display: "grid", gap: 18, alignContent: "start" }}><Card className="detail-section"><h2>Cheat sheet</h2><p className="eyebrow">Remember</p>{asStringArray(phase.cheat_sheet.remember).map((item) => <p key={item}>• {item}</p>)}<p className="eyebrow">Ask them</p>{asStringArray(phase.cheat_sheet.questions_to_ask).map((item) => <p key={item}>• {item}</p>)}</Card><Card className="detail-section"><Field label="Private round notes" htmlFor="phase-notes"><Textarea id="phase-notes" rows={10} value={notes} onChange={(event) => setNotes(event.target.value)} /></Field><Button style={{ marginTop: 12 }} variant="secondary" onClick={() => saveNotes.mutate()}>Save notes</Button></Card></aside></div>
    <Card className="detail-section"><div className="section-header"><div><h2>Post-round retrospective</h2><p>What you capture here changes the next round instead of disappearing into a notes file.</p></div><CheckCircle2 size={20}/></div><div className="form-grid"><Field label="How did it go?" htmlFor="reflection-went"><Textarea id="reflection-went" value={went} onChange={(event) => setWent(event.target.value)} /></Field><Field label="What surprised you?" htmlFor="reflection-surprise"><Textarea id="reflection-surprise" value={surprise} onChange={(event) => setSurprise(event.target.value)} /></Field><Field label="Difficult questions — one per line" htmlFor="reflection-difficult"><Textarea id="reflection-difficult" value={difficult} onChange={(event) => setDifficult(event.target.value)} /></Field><Field label="What did you learn about the team?" htmlFor="reflection-team"><Textarea id="reflection-team" value={learned} onChange={(event) => setLearned(event.target.value)} /></Field><Field label="What will you prepare differently?" htmlFor="reflection-different"><Textarea id="reflection-different" value={different} onChange={(event) => setDifferent(event.target.value)} /></Field></div><Button style={{ marginTop: 16 }} onClick={() => reflect.mutate()}>Complete round & adapt next prep</Button></Card>
  </div>;
}

function Practice({ prep }: { prep: InterviewPreparation }) {
  const queryClient = useQueryClient();
  const speech = useSpeech();
  const [phaseId, setPhaseId] = useState(prep.phases.find((item) => item.phase_number === prep.current_phase_number)?.id ?? prep.phases[0]?.id ?? "");
  const phase = prep.phases.find((item) => item.id === phaseId) ?? prep.phases[0];
  const [questionId, setQuestionId] = useState(phase?.questions[0]?.id ?? "");
  const question = phase?.questions.find((item) => item.id === questionId) ?? phase?.questions[0];
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<InterviewAttemptResult | null>(null);
  const startedAt = useRef<number | null>(null);
  const submit = useMutation({
    mutationFn: () => question ? platformApi.interviewIntelligence.submitAttempt(question.id, { answer_text: answer, transcript_source: speech.listening ? "BROWSER_SPEECH" : "TEXT", duration_seconds: startedAt.current ? Math.round((Date.now() - startedAt.current) / 1000) : null }) : Promise.reject(new Error("Question unavailable")),
    onSuccess: async (data) => { setResult(data); await queryClient.invalidateQueries({ queryKey: ["interview-intelligence", prep.job_id] }); toast.success(`Answer scored ${data.score}/100`); },
  });
  if (!phase || !question) return <Card className="detail-section"><p>No practice questions are available yet.</p></Card>;
  function changePhase(value: string) {
    setPhaseId(value);
    const next = prep.phases.find((item) => item.id === value);
    setQuestionId(next?.questions[0]?.id ?? ""); setAnswer(""); setResult(null);
  }
  return <div className="detail-grid"><div className="detail-main" style={{ display: "grid", gap: 18 }}><Card className="detail-section"><div className="form-grid"><Field label="Round" htmlFor="practice-phase"><NativeSelect id="practice-phase" value={phase.id} onChange={(event) => changePhase(event.target.value)}>{prep.phases.map((item) => <option key={item.id} value={item.id}>{item.phase_number}. {item.title}</option>)}</NativeSelect></Field><Field label="Question" htmlFor="practice-question"><NativeSelect id="practice-question" value={question.id} onChange={(event) => { setQuestionId(event.target.value); setAnswer(""); setResult(null); }}>{phase.questions.map((item) => <option key={item.id} value={item.id}>#{item.display_order} · {item.prompt.slice(0, 70)}</option>)}</NativeSelect></Field></div></Card><Card className="detail-section"><p className="eyebrow">{phase.phase_type.replaceAll("_", " ")}</p><h2>{question.prompt}</h2><div className="button-row" style={{ margin: "14px 0" }}><Button variant="secondary" onClick={() => speech.speakSegments([{ speaker: "Interviewer", text: question.prompt }])}><Volume2 size={16}/>Read question aloud</Button>{speech.listening ? <Button variant="danger" onClick={speech.stopDictation}><Pause size={16}/>Stop voice answer</Button> : <Button variant="secondary" onClick={() => { startedAt.current = Date.now(); speech.startDictation(setAnswer); }}><Mic size={16}/>Answer by voice</Button>}</div><Field label="Your answer" htmlFor="practice-answer" hint="Voice dictation fills this box when supported; typing always works."><Textarea id="practice-answer" rows={12} value={answer} onChange={(event) => setAnswer(event.target.value)} /></Field><Button style={{ marginTop: 14 }} disabled={!answer.trim() || submit.isPending} onClick={() => submit.mutate()}><Target size={16}/>Score answer</Button></Card>{result ? <Card className="detail-section"><div className="section-header"><div><p className="eyebrow">Adaptive feedback</p><h2>{result.score}/100</h2></div><Badge tone={result.score >= 80 ? "success" : result.score >= 60 ? "info" : "warning"}>Attempt complete</Badge></div><Progress value={result.score}/><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 18, marginTop: 18 }}><div><strong>Working</strong>{result.feedback.strengths?.map((item) => <p key={item}>✓ {item}</p>)}</div><div><strong>Improve next</strong>{result.feedback.improvements?.map((item) => <p key={item}>→ {item}</p>)}</div></div>{result.feedback.next_followup ? <div style={{ marginTop: 18, padding: 16, background: "var(--sage)", borderRadius: 8 }}><p className="eyebrow">Adaptive follow-up</p><strong>{result.feedback.next_followup}</strong></div> : null}<details style={{ marginTop: 16 }}><summary>Evidence-locked answer guidance</summary><p>{result.feedback.model_answer}</p></details></Card> : null}</div><aside className="detail-aside" style={{ display: "grid", gap: 18, alignContent: "start" }}><ReadinessCard prep={prep}/><Card className="detail-section"><h2>Scoring rubric</h2>{Object.entries(question.rubric).map(([name, weight]) => <div key={name} style={{ display: "flex", justifyContent: "space-between", margin: "9px 0" }}><span>{name}</span><strong>{weight}%</strong></div>)}</Card></aside></div>;
}

function Research({ prep }: { prep: InterviewPreparation }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [snippet, setSnippet] = useState("");
  const add = useMutation({ mutationFn: () => platformApi.interviewIntelligence.addResearchSource(prep.job_id, { source_kind: "REVIEWED_PUBLIC_SOURCE", title, url: url || null, snippet: snippet || null }), onSuccess: async () => { setTitle(""); setUrl(""); setSnippet(""); await queryClient.invalidateQueries({ queryKey: ["interview-intelligence", prep.job_id] }); toast.success("Research source added"); } });
  const company = asRecord(prep.company_research);
  const signals = Array.isArray(company.hiring_signals) ? company.hiring_signals as Array<Record<string, unknown>> : [];
  return <div style={{ display: "grid", gap: 18 }}><Card className="detail-section"><div className="section-header"><div><h2>Company intelligence</h2><p>Baseline signals are grounded in ApplyAI&apos;s canonical company and active job corpus; reviewed external sources can be layered in without contaminating verified candidate evidence.</p></div><Building2 size={20}/></div><div className="dashboard-grid">{signals.slice(0, 6).map((signal) => <Card key={String(signal.skill)} style={{ padding: 16 }}><p className="eyebrow">Hiring signal</p><h2>{String(signal.skill)}</h2><p>{metric(signal.job_mentions, "0")} job mentions</p></Card>)}</div></Card><Card className="detail-section"><div className="section-header"><div><h2>Add reviewed research</h2><p>Use this for current announcements, earnings, leadership updates, interviewer material, or team context you have verified.</p></div><UserRoundSearch size={20}/></div><div className="form-grid"><Field label="Source title" htmlFor="research-title"><Input id="research-title" value={title} onChange={(event) => setTitle(event.target.value)} /></Field><Field label="URL" htmlFor="research-url"><Input id="research-url" value={url} onChange={(event) => setUrl(event.target.value)} /></Field><Field label="Relevant excerpt / note" htmlFor="research-snippet" className="full-width"><Textarea id="research-snippet" value={snippet} onChange={(event) => setSnippet(event.target.value)} /></Field></div><Button style={{ marginTop: 14 }} disabled={!title.trim()} onClick={() => add.mutate()}>Add evidence source</Button></Card><div className="list-stack">{prep.research_sources.map((source) => <Card className="detail-section" key={source.id}><div className="section-header"><div><h2>{source.title}</h2><p>{source.source_kind.replaceAll("_", " ")}</p></div><Badge tone="success">Reviewed</Badge></div>{source.snippet ? <p>{source.snippet}</p> : null}{source.url ? <a href={source.url} target="_blank" rel="noreferrer">Open source ↗</a> : null}</Card>)}</div></div>;
}

function StoryBank() {
  const queryClient = useQueryClient();
  const stories = useQuery({ queryKey: ["interview-stories"], queryFn: platformApi.interviewIntelligence.stories });
  const [title, setTitle] = useState(""); const [situation, setSituation] = useState(""); const [task, setTask] = useState(""); const [action, setAction] = useState(""); const [result, setResult] = useState(""); const [skills, setSkills] = useState("");
  const create = useMutation({ mutationFn: () => platformApi.interviewIntelligence.createStory({ title, situation: situation || null, task: task || null, action: action || null, result: result || null, skills: skills.split(",").map((item) => item.trim()).filter(Boolean), categories: [], metrics: [], source_fact_ids: [], verified: false }), onSuccess: async () => { setTitle(""); setSituation(""); setTask(""); setAction(""); setResult(""); setSkills(""); await queryClient.invalidateQueries({ queryKey: ["interview-stories"] }); toast.success("Story added to your bank"); } });
  return <div style={{ display: "grid", gap: 18 }}><Card className="detail-section"><div className="section-header"><div><h2>Persistent story bank</h2><p>Build reusable STAR stories once, then bring the right evidence into future interviews.</p></div><BookOpen size={20}/></div><div className="form-grid"><Field label="Story title" htmlFor="story-title"><Input id="story-title" value={title} onChange={(event) => setTitle(event.target.value)} /></Field><Field label="Skills (comma separated)" htmlFor="story-skills"><Input id="story-skills" value={skills} onChange={(event) => setSkills(event.target.value)} /></Field><Field label="Situation" htmlFor="story-situation"><Textarea id="story-situation" value={situation} onChange={(event) => setSituation(event.target.value)} /></Field><Field label="Task" htmlFor="story-task"><Textarea id="story-task" value={task} onChange={(event) => setTask(event.target.value)} /></Field><Field label="Action" htmlFor="story-action"><Textarea id="story-action" value={action} onChange={(event) => setAction(event.target.value)} /></Field><Field label="Result" htmlFor="story-result"><Textarea id="story-result" value={result} onChange={(event) => setResult(event.target.value)} /></Field></div><Button style={{ marginTop: 14 }} disabled={!title.trim()} onClick={() => create.mutate()}>Save story</Button></Card>{stories.isLoading ? <Skeleton className="page-skeleton"/> : <div className="list-stack">{(stories.data ?? []).map((story) => <Card className="detail-section" key={String(story.id)}><div className="section-header"><div><h2>{String(story.title)}</h2><p>{Array.isArray(story.skills) ? story.skills.join(" · ") : "STAR evidence"}</p></div><Badge tone={story.verified ? "success" : "warning"}>{story.verified ? "Verified" : "Review"}</Badge></div><p><strong>Situation:</strong> {String(story.situation ?? "—")}</p><p><strong>Action:</strong> {String(story.action ?? "—")}</p><p><strong>Result:</strong> {String(story.result ?? "—")}</p></Card>)}</div>}</div>;
}

export function InterviewIntelligenceWorkspace({ jobId }: { jobId: string }) {
  const preparation = useQuery({ queryKey: ["interview-intelligence", jobId], queryFn: () => platformApi.interviewIntelligence.get(jobId), retry: false });
  if (preparation.isLoading) return <Skeleton className="page-skeleton" />;
  if (preparation.isError) {
    const missing = preparation.error instanceof PlatformApiError && preparation.error.status === 404;
    if (missing) return <><PageHeader eyebrow="Interview Intelligence" title="Build job-specific interview prep" description="Turn this job, company context and your verified Career Memory into a complete round-by-round preparation system."/><SetupCard jobId={jobId}/></>;
    return <ErrorState message={preparation.error.message} retry={() => preparation.refetch()} />;
  }
  const prep = preparation.data;
  return <>
    <PageHeader eyebrow="Interview Intelligence" title={prep.job.title} description="Company research, role and résumé analysis, a five-episode prep podcast, adaptive practice, quizzes, flashcards, round memory and readiness in one workspace." action={<Badge tone="success">{Number(prep.readiness?.overall ?? 45)}% ready</Badge>} />
    <Tabs defaultValue="overview">
      <TabsList aria-label="Interview workspace" style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
        {[["overview","Overview"],["podcast","Podcast"],["rounds","Rounds"],["practice","Practice"],["research","Research"],["stories","Story bank"],["setup","Setup"]].map(([value,label]) => <TabsTrigger key={value} value={value} className="ui-button ui-button-secondary ui-button-small">{label}</TabsTrigger>)}
      </TabsList>
      <TabsContent value="overview"><Overview prep={prep}/></TabsContent>
      <TabsContent value="podcast"><Podcast prep={prep}/></TabsContent>
      <TabsContent value="rounds"><Rounds prep={prep}/></TabsContent>
      <TabsContent value="practice"><Practice prep={prep}/></TabsContent>
      <TabsContent value="research"><Research prep={prep}/></TabsContent>
      <TabsContent value="stories"><StoryBank/></TabsContent>
      <TabsContent value="setup"><SetupCard jobId={jobId} initial={prep}/></TabsContent>
    </Tabs>
  </>;
}
