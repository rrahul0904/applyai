"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Code2, Database, Save, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, ErrorState, NativeSelect, Textarea } from "@/components/ui";
import { growthApi } from "@/lib/api/growth";

export function TechnicalInterviewLab({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const lab = useQuery({ queryKey: ["technical-interview-lab", jobId], queryFn: ({ signal }) => growthApi.interview.get(jobId, signal) });
  const [category, setCategory] = useState("TECHNICAL");
  const [selectedQuestion, setSelectedQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [notes, setNotes] = useState("");
  const questions = useMemo(() => (lab.data?.questions ?? []).filter((item) => category === "ALL" || item.category === category), [lab.data?.questions, category]);
  const question = selectedQuestion || questions[0]?.question || "";
  const save = useMutation({
    mutationFn: () => growthApi.interview.createAttempt({ job_id: jobId, category: category === "ALL" ? "TECHNICAL" : category, question, answer_text: answer || null, notes: notes || null, self_review: { truthful: true, reviewed_by_candidate: true } }),
    onSuccess: async () => {
      setAnswer(""); setNotes("");
      await queryClient.invalidateQueries({ queryKey: ["technical-interview-lab", jobId] });
      toast.success("Practice attempt saved");
    },
  });

  if (lab.isLoading) return <Card className="detail-section"><p>Loading Technical Interview Lab…</p></Card>;
  if (lab.isError || !lab.data) return <ErrorState message={lab.error?.message ?? "Technical Interview Lab is unavailable."} retry={() => lab.refetch()} />;

  return <Card className="detail-section">
    <div className="section-header"><div><p className="eyebrow">Technical Interview Lab</p><h2>Practice the work behind the role.</h2><p>Job-specific technical, SQL, system-design, coding-reasoning and behavioral prompts with durable attempt history.</p></div><Code2 size={24}/></div>
    <div className="form-grid">
      <label className="form-field"><span>Practice area</span><NativeSelect value={category} onChange={(event) => { setCategory(event.target.value); setSelectedQuestion(""); }}><option value="ALL">All prompts</option><option value="TECHNICAL">Technical</option><option value="SYSTEM_DESIGN">System design</option><option value="SQL">SQL</option><option value="CODING">Coding reasoning</option><option value="BEHAVIORAL">Behavioral / STAR</option></NativeSelect></label>
      <label className="form-field"><span>Question</span><NativeSelect value={question} onChange={(event) => setSelectedQuestion(event.target.value)}>{questions.map((item) => <option value={item.question} key={`${item.category}-${item.question}`}>{item.question}</option>)}</NativeSelect></label>
    </div>
    {question ? <><div className="detail-section"><Badge tone="info">{category === "ALL" ? "Mixed" : category}</Badge><p><strong>{question}</strong></p></div><label className="form-field"><span>Your answer / approach</span><Textarea value={answer} onChange={(event) => setAnswer(event.target.value)} rows={9} placeholder="Reason through the answer, trade-offs, edge cases, or a truthful STAR example." /></label><label className="form-field"><span>Review notes</span><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} placeholder="What would you strengthen next time?" /></label><Button onClick={() => save.mutate()} disabled={!question || save.isPending}><Save size={16}/>Save attempt</Button></> : null}
    <div className="detail-section"><p className="muted"><ShieldCheck size={15} style={{verticalAlign:"text-bottom"}} /> No arbitrary remote code is executed in the $0 launch. Coding questions emphasize approach, complexity, edge cases and candidate reasoning until a secure sandbox is justified.</p></div>
    {lab.data.attempts.length ? <><h3>Recent attempts</h3><div className="list-stack">{lab.data.attempts.slice(0, 8).map((attempt) => <article key={attempt.id}><div className="button-row"><Badge>{attempt.category}</Badge>{attempt.category === "SQL" ? <Database size={15}/> : <Code2 size={15}/>}</div><p><strong>{attempt.question}</strong></p>{attempt.answer_text ? <p className="muted">{attempt.answer_text}</p> : null}</article>)}</div></> : null}
  </Card>;
}
