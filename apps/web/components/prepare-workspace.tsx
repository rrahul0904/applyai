"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, BrainCircuit, CheckCircle2, Mic, Play, RefreshCw, Sparkles, Square, Video } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, EmptyState, ErrorState, Field, NativeSelect, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { prepareApi, type InterviewPack, type LearningPath, type MockInterview } from "@/lib/api/prepare-client";

type UploadIntent = {
  upload_mode: "DIRECT" | "PROXY";
  storage_key: string;
  upload_url: string;
  upload_headers: Record<string, string>;
  max_bytes: number;
};

type SpeechResult = { 0: { transcript: string }; isFinal?: boolean };
type SpeechResults = { length: number; [index: number]: SpeechResult };
type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: { results: SpeechResults }) => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

async function backendJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: init.body instanceof FormData ? init.headers : { "content-type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(body?.error?.message ?? "The request could not be completed.");
  }
  return response.json() as Promise<T>;
}

function scoreTone(score: number) {
  if (score >= 80) return "success" as const;
  if (score >= 60) return "info" as const;
  return "warning" as const;
}

function BionicText({ text, enabled }: { text: string; enabled: boolean }) {
  if (!enabled) return <div style={{ whiteSpace: "pre-wrap" }}>{text}</div>;
  return (
    <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.8 }}>
      {text.split(/(\s+)/).map((chunk, index) => {
        if (/^\s+$/.test(chunk)) return chunk;
        const pivot = Math.max(1, Math.ceil(chunk.length * 0.48));
        return <span key={`${chunk}-${index}`}><strong>{chunk.slice(0, pivot)}</strong>{chunk.slice(pivot)}</span>;
      })}
    </div>
  );
}

function ReadinessPanel({ jobId }: { jobId: string }) {
  const readiness = useQuery({ queryKey: ["prepare-readiness", jobId], queryFn: ({ signal }) => prepareApi.readiness(jobId, signal) });
  if (readiness.isLoading) return <Skeleton className="page-skeleton" />;
  if (readiness.isError) return <ErrorState message={readiness.error.message} retry={() => readiness.refetch()} />;
  if (!readiness.data) return null;
  return <>
    <div className="dashboard-grid">
      <Card><p className="eyebrow">Career readiness</p><h2>{readiness.data.overall_score}%</h2><Badge tone={scoreTone(readiness.data.overall_score)}>{readiness.data.band}</Badge></Card>
      {Object.entries(readiness.data.breakdown).map(([key, value]) => <Card key={key}><p className="eyebrow">{key}</p><h2>{value.score}%</h2><p className="muted">{value.weight}% of readiness</p></Card>)}
    </div>
    <Card className="detail-section"><h2>Next best actions</h2><div className="list-stack">{readiness.data.next_actions.map((item) => <div key={item} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}><CheckCircle2 size={17} style={{ marginTop: 3 }} /><span>{item}</span></div>)}</div></Card>
  </>;
}

function SkillGapPanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const gaps = useQuery({ queryKey: ["prepare-gaps", jobId], queryFn: ({ signal }) => prepareApi.skillGaps(jobId, signal) });
  const analyze = useMutation({
    mutationFn: () => prepareApi.analyzeSkills(jobId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["prepare-gaps", jobId] }),
        queryClient.invalidateQueries({ queryKey: ["prepare-readiness", jobId] }),
      ]);
      toast.success("Skill analysis refreshed");
    },
  });
  if (gaps.isLoading) return <Skeleton className="page-skeleton" />;
  if (gaps.isError) return <ErrorState message={gaps.error.message} retry={() => gaps.refetch()} />;
  return <Card className="detail-section">
    <div className="section-header"><div><h2>Skill intelligence</h2><p>Job requirements compared only against verified profile and learning evidence.</p></div><Button variant="secondary" onClick={() => analyze.mutate()} disabled={analyze.isPending}><RefreshCw size={15} />Re-analyze</Button></div>
    <div className="list-stack">{(gaps.data?.items ?? []).map((gap) => <div key={gap.id} style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
      <div className="section-header"><div><strong>{gap.skill}</strong><p className="muted">{gap.reason}</p></div><div className="button-row"><Badge tone={gap.status === "CLOSED" ? "success" : gap.severity === "HIGH" ? "warning" : "info"}>{gap.requirement_level}</Badge><Badge>{gap.candidate_level}</Badge></div></div>
      <p><strong>Next:</strong> {gap.recommended_action}</p>
    </div>)}{!gaps.data?.items.length ? <EmptyState title="No extracted skill requirements" description="This job does not yet have normalized skill requirements to compare." /> : null}</div>
  </Card>;
}

function CourseViewer({ courseId }: { courseId: string }) {
  const queryClient = useQueryClient();
  const course = useQuery({ queryKey: ["prepare-course", courseId], queryFn: ({ signal }) => prepareApi.course(courseId, signal) });
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null);
  const [bionic, setBionic] = useState(false);
  const [tutorQuestion, setTutorQuestion] = useState("");
  const [tutorAnswer, setTutorAnswer] = useState<string | null>(null);
  const [exerciseAnswer, setExerciseAnswer] = useState("");
  const [exerciseResult, setExerciseResult] = useState<{ score: number; feedback: Record<string, unknown> } | null>(null);
  const lessons = useMemo(() => course.data?.modules.flatMap((module) => module.lessons) ?? [], [course.data]);
  const lesson = lessons.find((item) => item.id === selectedLessonId) ?? lessons[0];
  const complete = useMutation({ mutationFn: (mastery: number | undefined) => lesson ? prepareApi.setLessonProgress(lesson.id, true, mastery) : Promise.resolve(null), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["prepare-course", courseId] }); toast.success("Lesson progress saved"); } });
  const tutor = useMutation({ mutationFn: () => lesson ? prepareApi.lessonChat(lesson.id, tutorQuestion) : Promise.reject(new Error("Select a lesson")), onSuccess: (data) => { setTutorAnswer(data.answer); setTutorQuestion(""); } });
  const exercise = lesson?.exercises[0];
  const attempt = useMutation({ mutationFn: () => exercise ? prepareApi.exerciseAttempt(exercise.id, exerciseAnswer) : Promise.reject(new Error("No exercise")), onSuccess: (data) => { setExerciseResult(data); complete.mutate(data.score); } });
  if (course.isLoading) return <Skeleton className="page-skeleton" />;
  if (course.isError) return <ErrorState message={course.error.message} retry={() => course.refetch()} />;
  if (!course.data || !lesson) return null;
  return <div className="detail-grid">
    <div className="detail-main">
      <Card className="detail-section"><div className="section-header"><div><p className="eyebrow">{course.data.skill}</p><h2>{lesson.title}</h2><p>{lesson.summary}</p></div><Button size="small" variant="secondary" onClick={() => setBionic((value) => !value)}>{bionic ? "Standard reading" : "Bionic reading"}</Button></div><BionicText text={lesson.content_markdown} enabled={bionic} /><div className="button-row" style={{ marginTop: 18 }}><Button onClick={() => complete.mutate(undefined)} disabled={lesson.completed || complete.isPending}>{lesson.completed ? "Completed" : "Mark complete"}</Button>{lesson.mastery_score !== null ? <Badge tone="success">Mastery {lesson.mastery_score}%</Badge> : null}</div></Card>
      <Card className="detail-section"><h2><BrainCircuit size={18} style={{ verticalAlign: "middle", marginRight: 8 }} />Lesson tutor</h2><Field label="Ask about this lesson" htmlFor="lesson-tutor"><Textarea id="lesson-tutor" rows={4} value={tutorQuestion} onChange={(event) => setTutorQuestion(event.target.value)} /></Field><Button onClick={() => tutor.mutate()} disabled={!tutorQuestion.trim() || tutor.isPending}>Ask tutor</Button>{tutorAnswer ? <div style={{ marginTop: 16, whiteSpace: "pre-wrap" }}>{tutorAnswer}</div> : null}</Card>
      {exercise ? <Card className="detail-section"><p className="eyebrow">{exercise.type}</p><h2>Practice</h2><p>{exercise.prompt}</p><Field label="Your answer" htmlFor="exercise-answer"><Textarea id="exercise-answer" rows={7} value={exerciseAnswer} onChange={(event) => setExerciseAnswer(event.target.value)} /></Field><Button onClick={() => attempt.mutate()} disabled={!exerciseAnswer.trim() || attempt.isPending}>Score answer</Button>{exerciseResult ? <div style={{ marginTop: 14 }}><Badge tone={scoreTone(exerciseResult.score)}>Score {exerciseResult.score}%</Badge><pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(exerciseResult.feedback, null, 2)}</pre></div> : null}</Card> : null}
    </div>
    <aside className="detail-aside"><Card className="sticky-actions"><h2>{course.data.title}</h2><p>{course.data.summary}</p><div className="list-stack">{lessons.map((item) => <Button key={item.id} variant={item.id === lesson.id ? "secondary" : "ghost"} onClick={() => { setSelectedLessonId(item.id); setTutorAnswer(null); setExerciseResult(null); }}>{item.completed ? "✓ " : ""}{item.title}</Button>)}</div></Card></aside>
  </div>;
}

function LearningPanel({ jobId }: { jobId: string }) {
  const [path, setPath] = useState<LearningPath | null>(null);
  const [courseId, setCourseId] = useState<string | null>(null);
  const create = useMutation({ mutationFn: () => prepareApi.createLearningPath(jobId), onSuccess: (data) => { setPath(data); setCourseId(data.courses[0]?.id ?? null); } });
  if (!path) return <Card className="detail-section"><div className="section-header"><div><h2>Personalized learning path</h2><p>Generate short role-specific courses only for skills that need evidence or interview practice.</p></div><Button onClick={() => create.mutate()} disabled={create.isPending}><BookOpen size={16}/>Build learning path</Button></div></Card>;
  return <><Card className="detail-section"><div className="section-header"><div><p className="eyebrow">{path.estimated_minutes} minutes planned</p><h2>{path.title}</h2></div><Badge tone="info">{path.courses.length} courses</Badge></div><div className="button-row">{path.courses.map((course) => <Button key={course.id} size="small" variant={courseId === course.id ? "secondary" : "ghost"} onClick={() => setCourseId(course.id)}>{course.skill}</Button>)}</div></Card>{courseId ? <CourseViewer courseId={courseId} /> : null}</>;
}

function InterviewPackPanel({ jobId }: { jobId: string }) {
  const [pack, setPack] = useState<InterviewPack | null>(null);
  const create = useMutation({ mutationFn: () => prepareApi.createInterviewPack(jobId), onSuccess: setPack });
  if (!pack) return <Card className="detail-section"><div className="section-header"><div><h2>Interview book</h2><p>Technical cheatsheets, Q&A, practical tasks, behavioral prompts, resume deep dives and questions to ask.</p></div><Button onClick={() => create.mutate()} disabled={create.isPending}><Sparkles size={16}/>Generate interview book</Button></div></Card>;
  return <><Card className="detail-section"><p className="eyebrow">Evidence-grounded prep</p><h2>{pack.title}</h2><p>{pack.strategy_summary}</p></Card><div className="dashboard-grid">{pack.sections.map((section) => <Card key={section.type}><p className="eyebrow">{section.type.replaceAll("_", " ")}</p><h2>{section.title}</h2><pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{JSON.stringify(section.content, null, 2)}</pre></Card>)}</div></>;
}

function MockInterviewPanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState("technical");
  const [channel, setChannel] = useState<"WRITTEN" | "VOICE" | "VIDEO">("WRITTEN");
  const [mock, setMock] = useState<MockInterview | null>(null);
  const [answer, setAnswer] = useState("");
  const [recording, setRecording] = useState<Blob | null>(null);
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recordingActive, setRecordingActive] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = useMutation({ mutationFn: () => prepareApi.startMock(jobId, mode, channel), onSuccess: (data) => { setMock(data); setAnswer(""); setRecording(null); setRecordingUrl(null); } });
  const answerMutation = useMutation({ mutationFn: () => mock ? prepareApi.answerMock(mock.id, answer) : Promise.reject(new Error("Start an interview")), onSuccess: (data) => { setMock(data); setAnswer(""); } });
  const complete = useMutation({ mutationFn: () => mock ? prepareApi.completeMock(mock.id) : Promise.reject(new Error("Start an interview")), onSuccess: async (data) => { setMock(data); await queryClient.invalidateQueries({ queryKey: ["prepare-readiness", jobId] }); } });
  const currentQuestion = mock?.current_question ?? null;

  const speakQuestion = useCallback(() => {
    if (!currentQuestion || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(currentQuestion.question));
  }, [currentQuestion]);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  function startBrowserTranscription() {
    const speechWindow = window as unknown as { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
    const Constructor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Constructor) return;
    const recognition = new Constructor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) transcript += `${event.results[index][0].transcript} `;
      if (transcript.trim()) setAnswer(transcript.trim());
    };
    recognition.onerror = () => toast.message("Live transcription is unavailable in this browser. The recording can still be saved and the transcript can be typed manually.");
    recognitionRef.current = recognition;
    recognition.start();
  }

  async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: channel === "VIDEO" });
    mediaStreamRef.current = stream;
    chunksRef.current = [];
    const preferred = channel === "VIDEO" ? "video/webm" : "audio/webm";
    const recorder = new MediaRecorder(stream, MediaRecorder.isTypeSupported(preferred) ? { mimeType: preferred } : undefined);
    recorderRef.current = recorder;
    startTimeRef.current = Date.now();
    recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
    recorder.onstop = () => {
      const type = recorder.mimeType || preferred;
      const blob = new Blob(chunksRef.current, { type });
      setRecording(blob);
      if (recordingUrl) URL.revokeObjectURL(recordingUrl);
      setRecordingUrl(URL.createObjectURL(blob));
      setRecordingSeconds(Math.max(1, Math.round((Date.now() - (startTimeRef.current ?? Date.now())) / 1000)));
      setRecordingActive(false);
      stream.getTracks().forEach((track) => track.stop());
    };
    recorder.start(500);
    setRecordingActive(true);
    startBrowserTranscription();
  }

  function stopRecording() {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    recorderRef.current?.stop();
    setRecordingActive(false);
  }

  async function uploadRecording() {
    if (!mock || !recording) return;
    const contentType = recording.type || (channel === "VIDEO" ? "video/webm" : "audio/webm");
    const intent = await backendJson<UploadIntent>(`/api/v1/career-v2/interviews/${mock.id}/recording-upload-intents`, { method: "POST", body: JSON.stringify({ filename: channel === "VIDEO" ? "mock-interview.webm" : "mock-interview-audio.webm", content_type: contentType, file_size: recording.size, media_type: channel === "VIDEO" ? "VIDEO" : "AUDIO" }) });
    if (intent.upload_mode === "DIRECT") {
      const uploaded = await fetch(intent.upload_url, { method: "PUT", headers: intent.upload_headers, body: recording });
      if (!uploaded.ok) throw new Error("Recording upload failed");
    } else {
      const body = new FormData();
      body.append("file", recording, "mock-interview.webm");
      const uploaded = await fetch(intent.upload_url, { method: "POST", body });
      if (!uploaded.ok) throw new Error("Recording upload failed");
    }
    await backendJson(`/api/v1/career-v2/interviews/${mock.id}/recording-upload-complete`, { method: "POST", body: JSON.stringify({ storage_key: intent.storage_key, media_type: channel === "VIDEO" ? "VIDEO" : "AUDIO", transcript_text: answer.trim() || null, duration_seconds: recordingSeconds, provider: "browser-media-recorder" }) });
    toast.success("Interview recording saved privately");
  }

  return <Card className="detail-section">
    <div className="section-header"><div><h2>Adaptive mock interview</h2><p>Written, voice, or video practice with per-answer scoring and follow-up questions.</p></div>{mock?.overall_score !== null && mock?.overall_score !== undefined ? <Badge tone={scoreTone(mock.overall_score)}>Overall {mock.overall_score}%</Badge> : null}</div>
    {!mock ? <div className="form-grid"><Field label="Mode" htmlFor="mock-mode"><NativeSelect id="mock-mode" value={mode} onChange={(event) => setMode(event.target.value)}><option value="technical">Technical</option><option value="behavioral">Behavioral</option><option value="system_design">System design</option><option value="coding">Coding</option><option value="sql">SQL</option></NativeSelect></Field><Field label="Channel" htmlFor="mock-channel"><NativeSelect id="mock-channel" value={channel} onChange={(event) => setChannel(event.target.value as "WRITTEN" | "VOICE" | "VIDEO")}><option>WRITTEN</option><option>VOICE</option><option>VIDEO</option></NativeSelect></Field><div className="button-row"><Button onClick={() => start.mutate()} disabled={start.isPending}><Play size={16}/>Start mock</Button></div></div> : null}
    {currentQuestion ? <div className="list-stack">
      <div><p className="eyebrow">Question {currentQuestion.position}</p><h2>{currentQuestion.question}</h2>{channel !== "WRITTEN" ? <Button size="small" variant="ghost" onClick={speakQuestion}><Play size={14}/>Read aloud</Button> : null}</div>
      {channel !== "WRITTEN" ? <div className="button-row">{recordingActive ? <Button variant="secondary" onClick={stopRecording}><Square size={15}/>Stop recording</Button> : <Button variant="secondary" onClick={() => startRecording().catch((error: Error) => toast.error(error.message))}>{channel === "VIDEO" ? <Video size={15}/> : <Mic size={15}/>}Record answer</Button>}{recordingUrl ? channel === "VIDEO" ? <video src={recordingUrl} controls style={{ width: 300, maxWidth: "100%" }} /> : <audio src={recordingUrl} controls /> : null}</div> : null}
      <Field label={channel === "WRITTEN" ? "Your answer" : "Live transcript used for scoring"} htmlFor="mock-answer"><Textarea id="mock-answer" rows={8} value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder={channel === "WRITTEN" ? "Answer as you would in the interview…" : "Supported browsers transcribe your recording live. You can correct the transcript before scoring."} /></Field>
      <div className="button-row"><Button onClick={() => answerMutation.mutate()} disabled={!answer.trim() || answerMutation.isPending}>Score & continue</Button>{recording ? <Button variant="secondary" onClick={() => uploadRecording().catch((error: Error) => toast.error(error.message))}>Save recording</Button> : null}<Button variant="ghost" onClick={() => complete.mutate()} disabled={complete.isPending}>Finish interview</Button></div>
    </div> : null}
    {mock?.status === "COMPLETED" ? <div className="list-stack"><h3>Interview report</h3><pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{JSON.stringify({ category_scores: mock.category_scores, feedback: mock.feedback }, null, 2)}</pre>{mock.turns.map((turn) => <div key={turn.id} style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}><strong>{turn.question}</strong><p>{turn.answer}</p><Badge tone={scoreTone(turn.score ?? 0)}>{turn.score ?? 0}%</Badge><pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{JSON.stringify(turn.evaluation, null, 2)}</pre></div>)}</div> : null}
  </Card>;
}

export function PrepareWorkspace({ jobId }: { jobId: string }) {
  const [tab, setTab] = useState<"overview" | "skills" | "learn" | "prep" | "mock">("overview");
  return <>
    <PageHeader eyebrow="ApplyAI Prepare" title="Turn this job into an interview plan" description="One job-scoped workspace for skill gaps, micro-learning, interview books, adaptive mocks, recordings, scoring and readiness." />
    <div className="button-row" style={{ marginBottom: 18 }}>{(["overview", "skills", "learn", "prep", "mock"] as const).map((item) => <Button key={item} size="small" variant={tab === item ? "secondary" : "ghost"} onClick={() => setTab(item)}>{item === "prep" ? "Interview prep" : item.charAt(0).toUpperCase() + item.slice(1)}</Button>)}</div>
    {tab === "overview" ? <ReadinessPanel jobId={jobId} /> : null}
    {tab === "skills" ? <SkillGapPanel jobId={jobId} /> : null}
    {tab === "learn" ? <LearningPanel jobId={jobId} /> : null}
    {tab === "prep" ? <InterviewPackPanel jobId={jobId} /> : null}
    {tab === "mock" ? <MockInterviewPanel jobId={jobId} /> : null}
  </>;
}
