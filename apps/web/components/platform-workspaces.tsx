"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Download, Plus, Sparkles, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api/client";
import { platformApi, type ResumeDocument } from "@/lib/api/platform-client";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, NativeSelect, PageHeader, Skeleton, Textarea } from "@/components/ui";

export function MatchesWorkspace() {
  const semantic = useQuery({ queryKey: ["semantic-matches"], queryFn: () => platformApi.semanticMatches(40) });
  const hybrid = useQuery({ queryKey: ["career-v2-matches"], queryFn: ({ signal }) => api.careerV2.matches(signal) });
  if (semantic.isLoading || hybrid.isLoading) return <Skeleton className="page-skeleton" />;
  if (semantic.isError) return <ErrorState message={semantic.error.message} retry={() => semantic.refetch()} />;
  const hybridByJob = new Map((hybrid.data?.items ?? []).map((item) => [item.job_id, item]));
  return <>
    <PageHeader eyebrow="Opportunity intelligence" title="AI Matches" description="Semantic relevance plus ApplyAI's explainable Career Intelligence score. Scores prioritize your search; they are not hiring probabilities." />
    <div className="list-stack">
      {(semantic.data?.items ?? []).map((item) => {
        const career = hybridByJob.get(item.job_id);
        return <Card key={item.job_id} className="detail-section">
          <div className="section-header"><div><h2>{item.title}</h2><p>{item.company}</p></div><div className="button-row"><Badge tone="info">Semantic {Math.max(0, Math.round(item.semantic_score))}</Badge>{career ? <Badge tone="success">Career {Math.round(career.final_score)}</Badge> : null}</div></div>
          <p className="muted">{item.explanation}</p>
          {career ? <p><strong>{career.decision}</strong> · {career.fit_band} · {career.confidence} confidence</p> : null}
          <div className="button-row"><Link className="ui-button ui-button-primary ui-button-small" href={`/jobs/${item.job_id}`}>Review job</Link><Link className="ui-button ui-button-secondary ui-button-small" href={`/interview/${item.job_id}`}>Interview prep</Link></div>
        </Card>;
      })}
      {!semantic.data?.items.length ? <EmptyState title="No matches yet" description="Complete your profile and Career Memory, then ApplyAI can rank active roles against your verified goals and evidence." /> : null}
    </div>
  </>;
}

function resumeText(document: ResumeDocument | null) {
  const content = document?.content ?? {};
  return typeof content.summary === "string" ? content.summary : "";
}

export function ResumeStudioWorkspace() {
  const queryClient = useQueryClient();
  const docs = useQuery({ queryKey: ["resume-studio"], queryFn: platformApi.resumeStudio.list });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = useMemo(() => docs.data?.find((item) => item.id === selectedId) ?? docs.data?.[0] ?? null, [docs.data, selectedId]);
  const [draftSummary, setDraftSummary] = useState("");
  const create = useMutation({ mutationFn: () => platformApi.resumeStudio.create({ title: "New resume variant", content: { summary: "", sections: [] } }), onSuccess: async (item) => { setSelectedId(item.id); setDraftSummary(""); await queryClient.invalidateQueries({ queryKey: ["resume-studio"] }); toast.success("Resume variant created"); } });
  const save = useMutation({ mutationFn: async () => { if (!selected) return; return platformApi.resumeStudio.update(selected.id, { content: { ...selected.content, summary: draftSummary || resumeText(selected) }, status: "REVIEWED" }); }, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["resume-studio"] }); toast.success("Resume saved"); } });
  const exportDoc = useMutation({ mutationFn: async () => { if (!selected) return null; return platformApi.resumeStudio.export(selected.id, "txt"); }, onSuccess: (file) => { if (!file) return; const blob = new Blob([file.content], { type: file.content_type }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = file.filename; anchor.click(); URL.revokeObjectURL(url); } });
  if (docs.isLoading) return <Skeleton className="page-skeleton" />;
  if (docs.isError) return <ErrorState message={docs.error.message} retry={() => docs.refetch()} />;
  return <>
    <PageHeader eyebrow="Evidence-locked documents" title="Resume Studio" description="Maintain multiple job-specific resume variants, review edits, version changes and export candidate-approved content." action={<Button onClick={() => create.mutate()} disabled={create.isPending}><Plus size={16}/>New variant</Button>} />
    <div className="detail-grid">
      <div className="detail-main"><Card className="detail-section">
        {selected ? <>
          <div className="section-header"><div><h2>{selected.title}</h2><p>Version {selected.version} · {selected.status}</p></div><Badge tone={selected.status === "FINAL" ? "success" : "info"}>{selected.status}</Badge></div>
          <Field label="Professional summary" htmlFor="resume-summary"><Textarea id="resume-summary" value={draftSummary || resumeText(selected)} onChange={(event) => setDraftSummary(event.target.value)} rows={10}/></Field>
          <p className="muted">Verified Career Memory evidence remains attached to job-created variants and is never silently converted into unsupported claims.</p>
          <div className="button-row"><Button onClick={() => save.mutate()} disabled={save.isPending}>Save revision</Button><Button variant="secondary" onClick={() => exportDoc.mutate()}><Download size={16}/>Export TXT</Button></div>
        </> : <EmptyState title="Create your first resume variant" description="Use a master resume or a specific job as the starting point, then review every AI-assisted change." />}
      </Card></div>
      <aside className="detail-aside"><Card className="sticky-actions"><h2>Variants</h2><div className="list-stack">{(docs.data ?? []).map((item) => <Button key={item.id} variant={selected?.id === item.id ? "secondary" : "ghost"} onClick={() => { setSelectedId(item.id); setDraftSummary(""); }}>{item.title} · v{item.version}</Button>)}</div></Card></aside>
    </div>
  </>;
}

export function NetworkWorkspace() {
  const queryClient = useQueryClient(); const contacts = useQuery({ queryKey: ["contacts"], queryFn: platformApi.contacts.list });
  const [name, setName] = useState(""); const [company, setCompany] = useState(""); const [email, setEmail] = useState("");
  const create = useMutation({ mutationFn: () => platformApi.contacts.create({ name, company: company || null, email: email || null }), onSuccess: async () => { setName(""); setCompany(""); setEmail(""); await queryClient.invalidateQueries({ queryKey: ["contacts"] }); toast.success("Contact saved"); } });
  const remove = useMutation({ mutationFn: platformApi.contacts.remove, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts"] }) });
  if (contacts.isLoading) return <Skeleton className="page-skeleton" />;
  return <><PageHeader eyebrow="Career relationships" title="Network" description="Track recruiters, hiring managers, referrals and follow-up dates alongside your applications." />
    <Card className="detail-section"><form className="form-grid" onSubmit={(event) => { event.preventDefault(); if (name.trim()) create.mutate(); }}><Field label="Name" htmlFor="contact-name"><Input id="contact-name" value={name} onChange={(e) => setName(e.target.value)} /></Field><Field label="Company" htmlFor="contact-company"><Input id="contact-company" value={company} onChange={(e) => setCompany(e.target.value)} /></Field><Field label="Email" htmlFor="contact-email"><Input id="contact-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field><div className="button-row"><Button type="submit" disabled={!name.trim()}>Add contact</Button></div></form></Card>
    <div className="list-stack">{(contacts.data ?? []).map((contact) => <Card className="detail-section" key={contact.id}><div className="section-header"><div><h2>{contact.name}</h2><p>{[contact.title, contact.company].filter(Boolean).join(" · ") || "Career contact"}</p></div><Button variant="ghost" size="small" onClick={() => remove.mutate(contact.id)}><Trash2 size={15}/>Remove</Button></div><p>{contact.email ?? "No email saved"}</p>{contact.followup_at ? <Badge tone="warning">Follow-up scheduled</Badge> : null}</Card>)}</div>
  </>;
}

export function AnalyticsWorkspace() {
  const analytics = useQuery({ queryKey: ["candidate-analytics"], queryFn: platformApi.analytics });
  if (analytics.isLoading) return <Skeleton className="page-skeleton" />;
  if (analytics.isError) return <ErrorState message={analytics.error.message} retry={() => analytics.refetch()} />;
  const data = analytics.data ?? {};
  const cards = [
    ["Saved jobs", data.saved_jobs], ["Resume variants", data.resume_documents], ["Interview practices", data.interview_practice_sessions], ["Network contacts", data.network_contacts], ["Unread alerts", data.unread_notifications],
  ];
  return <><PageHeader eyebrow="Search performance" title="Candidate Analytics" description="Understand the activity behind your job search and where the funnel needs attention." /><div className="dashboard-grid">{cards.map(([label, value]) => <Card key={String(label)}><p className="eyebrow">{String(label)}</p><h2>{String(value ?? 0)}</h2></Card>)}</div><Card className="detail-section"><h2>Application funnel</h2><pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(data.applications ?? {}, null, 2)}</pre></Card></>;
}

export function AlertsWorkspace() {
  const queryClient = useQueryClient(); const notifications = useQuery({ queryKey: ["notifications"], queryFn: platformApi.notifications.list }); const searches = useQuery({ queryKey: ["saved-searches"], queryFn: platformApi.savedSearches.list });
  const [name, setName] = useState(""); const [keyword, setKeyword] = useState("");
  const create = useMutation({ mutationFn: () => platformApi.savedSearches.create({ name, query: { q: keyword }, alerts_enabled: true, minimum_match_score: 70 }), onSuccess: async () => { setName(""); setKeyword(""); await queryClient.invalidateQueries({ queryKey: ["saved-searches"] }); toast.success("Job alert saved"); } });
  const markRead = useMutation({ mutationFn: platformApi.notifications.read, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }) });
  return <><PageHeader eyebrow="Stay ahead" title="Alerts & Follow-ups" description="Saved searches, job-match alerts, interview reminders and recruiter follow-ups in one inbox." />
    <Card className="detail-section"><form className="form-grid" onSubmit={(event) => { event.preventDefault(); if (name && keyword) create.mutate(); }}><Field label="Alert name" htmlFor="alert-name"><Input id="alert-name" value={name} onChange={(e) => setName(e.target.value)} /></Field><Field label="Keyword" htmlFor="alert-keyword"><Input id="alert-keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} /></Field><div className="button-row"><Button type="submit"><Bell size={16}/>Create alert</Button></div></form><div className="list-stack" style={{marginTop:16}}>{(searches.data ?? []).map((search) => <div key={search.id}><strong>{search.name}</strong> · minimum match {search.minimum_match_score}</div>)}</div></Card>
    <div className="list-stack">{(notifications.data ?? []).map((item) => <Card className="detail-section" key={item.id}><div className="section-header"><div><h2>{item.title}</h2><p>{item.body}</p></div>{item.read_at ? <Badge>Read</Badge> : <Button size="small" variant="secondary" onClick={() => markRead.mutate(item.id)}>Mark read</Button>}</div>{item.action_url ? <Link href={item.action_url} className="ui-button ui-button-ghost ui-button-small">Open</Link> : null}</Card>)}</div>
  </>;
}

export function InterviewWorkspace({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient(); const sessions = useQuery({ queryKey: ["interview-practice", jobId], queryFn: () => platformApi.interview.list(jobId) });
  const [mode, setMode] = useState("MIXED"); const [answer, setAnswer] = useState("");
  const create = useMutation({ mutationFn: () => platformApi.interview.create({ job_id: jobId, mode, responses: [] }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["interview-practice", jobId] }) });
  const generate = useMutation({ mutationFn: () => api.careerV2.start(jobId, "interview-prep"), onSuccess: () => toast.success("Interview preparation is being generated") });
  const current = sessions.data?.[0] as { id?: string; responses?: Array<Record<string, unknown>>; score?: number } | undefined;
  const saveAnswer = useMutation({ mutationFn: () => current?.id ? platformApi.interview.update(current.id, { responses: [...(current.responses ?? []), { question: "Practice answer", answer }] }) : Promise.resolve({}), onSuccess: async () => { setAnswer(""); await queryClient.invalidateQueries({ queryKey: ["interview-practice", jobId] }); } });
  return <><PageHeader eyebrow="Job-specific preparation" title="Interview Copilot" description="Generate evidence-grounded prep, practice answers and retain feedback for this role." action={<Button onClick={() => generate.mutate()}><Sparkles size={16}/>Generate AI prep</Button>} />
    <Card className="detail-section"><div className="form-grid"><Field label="Practice mode" htmlFor="practice-mode"><NativeSelect id="practice-mode" value={mode} onChange={(e) => setMode(e.target.value)}><option>MIXED</option><option>BEHAVIORAL</option><option>TECHNICAL</option><option>SYSTEM_DESIGN</option><option>MANAGER</option></NativeSelect></Field><div className="button-row"><Button variant="secondary" onClick={() => create.mutate()}>Start session</Button></div></div>{current ? <><p>Current readiness score: <strong>{String(current.score ?? "Not scored")}</strong></p><Field label="Practice response" htmlFor="practice-answer"><Textarea id="practice-answer" value={answer} onChange={(e) => setAnswer(e.target.value)} rows={8}/></Field><Button disabled={!answer.trim()} onClick={() => saveAnswer.mutate()}>Save practice answer</Button></> : null}</Card>
  </>;
}

export function BillingWorkspace() {
  const subscription = useQuery({ queryKey: ["billing-subscription"], queryFn: platformApi.billing.subscription });
  if (subscription.isLoading) return <Skeleton className="page-skeleton" />;
  const data = subscription.data ?? {};
  return <><PageHeader eyebrow="Pilot access" title="Free validation plan" description="ApplyAI is operating as a non-commercial, zero-cost pilot. Paid plans and checkout are disabled." /><Card className="detail-section"><div className="section-header"><div><h2>{String(data.plan ?? "FREE")}</h2><p>Status: {String(data.status ?? "ACTIVE")}</p></div><Badge tone="info">Zero-cost pilot</Badge></div><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(data.entitlements ?? {}, null, 2)}</pre></Card></>;
}
