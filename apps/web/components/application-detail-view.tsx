"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api/client";
import { Badge, Button, Card, ErrorState, Field, NativeSelect, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { formatDate, titleCase } from "@/lib/utils";

const statuses = ["PREPARING", "READY", "APPLIED", "RECRUITER_SCREEN", "ASSESSMENT", "INTERVIEW", "FINAL_INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"];

export function ApplicationDetailView({ applicationId }: { applicationId: string }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const application = useQuery({
    queryKey: ["application", applicationId],
    queryFn: ({ signal }) => api.applications.detail(applicationId, signal),
  });
  const job = useQuery({
    queryKey: ["job", application.data?.job_id],
    queryFn: ({ signal }) => api.jobs.detail(application.data!.job_id, signal),
    enabled: Boolean(application.data?.job_id),
  });
  const statusMutation = useMutation({
    mutationFn: (status: string) => api.applications.updateStatus(applicationId, status),
    onSuccess: (data) => {
      queryClient.setQueryData(["application", applicationId], data);
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      toast.success("Application status updated");
    },
    onError: () => toast.error("We couldn't update this application."),
  });
  const noteMutation = useMutation({
    mutationFn: (body: string) => api.applications.addNote(applicationId, body),
    onSuccess: async () => {
      setNote("");
      await queryClient.invalidateQueries({ queryKey: ["application", applicationId] });
      await queryClient.invalidateQueries({ queryKey: ["applications"] });
      toast.success("Note added");
    },
    onError: () => toast.error("We couldn't add that note."),
  });
  const deleteNote = useMutation({
    mutationFn: (noteId: string) => api.applications.deleteNote(applicationId, noteId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["application", applicationId] }),
    onError: () => toast.error("We couldn't delete that note."),
  });

  if (application.isLoading || job.isLoading) return <Skeleton className="page-skeleton" />;
  if (application.isError || job.isError || !application.data || !job.data) return <ErrorState message={application.error?.message ?? job.error?.message} retry={() => { application.refetch(); job.refetch(); }} />;

  const app = application.data;
  const posting = job.data;
  return (
    <>
      <PageHeader eyebrow="Application workspace" title={posting.title} description={`${posting.company_name} · ${posting.location ?? "Location flexible"}`} action={<Link className="ui-button ui-button-secondary ui-button-small" href={`/jobs/${posting.id}`}>View job</Link>} />
      <div className="detail-grid">
        <div className="detail-main">
          <Card className="detail-section">
            <div className="section-header"><div><h2>Timeline</h2><p>Application history is append-only.</p></div><Badge tone="info">{titleCase(app.current_status)}</Badge></div>
            <ol className="timeline">
              {(app.events ?? []).map((event) => <li key={event.id}><span className="timeline-dot" aria-hidden="true" /><div><strong>{event.from_status ? `${titleCase(event.from_status)} → ${titleCase(event.to_status)}` : `Application created as ${titleCase(event.to_status)}`}</strong><time>{formatDate(event.created_at)}</time></div></li>)}
            </ol>
          </Card>
          <Card className="detail-section">
            <h2>Notes</h2>
            <form className="form-stack" onSubmit={(event) => { event.preventDefault(); if (note.trim()) noteMutation.mutate(note.trim()); }}>
              <Field label="Add a private note" htmlFor="application-note"><Textarea id="application-note" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Interview follow-up, recruiter details, next steps…" /></Field>
              <div className="button-row"><Button disabled={!note.trim() || noteMutation.isPending} type="submit">Add note</Button></div>
            </form>
            <div className="list-stack" style={{ marginTop: 20 }}>
              {(app.notes ?? []).map((item) => <div className="note" key={item.id}><p>{item.body}</p><div className="note-footer"><span>Updated {formatDate(item.updated_at)}</span><Button variant="ghost" size="small" aria-label="Delete note" onClick={() => deleteNote.mutate(item.id)}><Trash2 size={15} />Delete</Button></div></div>)}
              {!(app.notes ?? []).length ? <p className="muted">No notes yet.</p> : null}
            </div>
          </Card>
        </div>
        <aside className="detail-aside">
          <Card className="sticky-actions">
            <Field label="Application status" htmlFor="application-status"><NativeSelect id="application-status" value={app.current_status} disabled={statusMutation.isPending} onChange={(event) => statusMutation.mutate(event.target.value)}>{statuses.map((status) => <option value={status} key={status}>{titleCase(status)}</option>)}</NativeSelect></Field>
            <div className="facts-list">
              <div className="fact-row"><CalendarDays size={17} /><div><strong>Tracking started</strong><span>{formatDate(app.created_at)}</span></div></div>
              <div className="fact-row"><CalendarDays size={17} /><div><strong>Last updated</strong><span>{formatDate(app.updated_at)}</span></div></div>
            </div>
          </Card>
        </aside>
      </div>
    </>
  );
}
