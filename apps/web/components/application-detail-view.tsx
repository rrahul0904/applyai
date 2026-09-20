"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Share2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { api, type ApplicationTrackerWrite } from "@/lib/api/client";
import { ApplicationWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { ApplicationAgentPanel } from "@/components/application-agent-panel";
import { ApplicationSubmissionPanel } from "@/components/application-submission-panel";
import { Badge, Button, Card, ErrorState, Field, Input, NativeSelect, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { formatDate, titleCase } from "@/lib/utils";

const statuses = ["PREPARING", "READY", "APPLIED", "RECRUITER_SCREEN", "ASSESSMENT", "INTERVIEW", "FINAL_INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"];

function localDateTimeValue(value?: string | null) {
  return value ? value.slice(0, 16) : "";
}

function toIsoOrNull(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text ? new Date(text).toISOString() : null;
}

function toNumberOrNull(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  if (!text) return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
}

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
  const trackerMutation = useMutation({
    mutationFn: (payload: ApplicationTrackerWrite) => api.applications.updateTracker(applicationId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["application", applicationId] });
      await queryClient.invalidateQueries({ queryKey: ["applications"] });
      toast.success("Opportunity details updated");
    },
    onError: () => toast.error("We couldn't update the opportunity details."),
  });

  if (application.isLoading || job.isLoading) return <Skeleton className="page-skeleton" />;
  if (application.isError || job.isError || !application.data || !job.data) return <ErrorState message={application.error?.message ?? job.error?.message} retry={() => { application.refetch(); job.refetch(); }} />;

  const app = application.data;
  const posting = job.data;
  const shareHref = `/resume/signals?jobId=${encodeURIComponent(posting.id)}&applicationId=${encodeURIComponent(applicationId)}&label=${encodeURIComponent(`${posting.company_name} — ${posting.title}`)}&channel=application`;
  return (
    <>
      <ApplicationWorkspaceTabs activeHref="/applications" />
      <PageHeader
        eyebrow="Opportunity workspace"
        title={posting.title}
        description={`${posting.company_name} · ${posting.location ?? "Location flexible"} · keep preparation, follow-up, and evidence connected here.`}
        action={<Link className="ui-button ui-button-secondary ui-button-small" href={`/jobs/${posting.id}`}>View job intelligence</Link>}
      />
      <div className="cx-application-status-strip">
        <span>Current stage</span>
        <Badge tone={app.current_status === "OFFER" ? "success" : app.current_status === "REJECTED" ? "danger" : "info"}>{titleCase(app.current_status)}</Badge>
        <span>Last updated {formatDate(app.updated_at)}</span>
      </div>
      <div className="detail-grid">
        <div className="detail-main">
          <ApplicationAgentPanel applicationId={applicationId} jobId={posting.id} />
          <ApplicationSubmissionPanel applicationId={applicationId} jobId={posting.id} sourceUrl={posting.source_url} />
          <Card className="detail-section">
            <div className="section-header"><div><h2>Progress</h2><p>A simple history of how this opportunity has moved.</p></div></div>
            <ol className="timeline">
              {(app.events ?? []).map((event) => <li key={event.id}><span className="timeline-dot" aria-hidden="true" /><div><strong>{event.from_status ? `${titleCase(event.from_status)} → ${titleCase(event.to_status)}` : `Started as ${titleCase(event.to_status)}`}</strong><time>{formatDate(event.created_at)}</time></div></li>)}
            </ol>
          </Card>
          <Card className="detail-section">
            <h2>Notes & follow-ups</h2>
            <form className="form-stack" onSubmit={(event) => { event.preventDefault(); if (note.trim()) noteMutation.mutate(note.trim()); }}>
              <Field label="Add a private note" htmlFor="application-note"><Textarea id="application-note" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Recruiter details, interview notes, follow-up reminders…" /></Field>
              <div className="button-row"><Button disabled={!note.trim() || noteMutation.isPending} type="submit">Save note</Button></div>
            </form>
            <div className="list-stack" style={{ marginTop: 20 }}>
              {(app.notes ?? []).map((item) => <div className="note" key={item.id}><p>{item.body}</p><div className="note-footer"><span>Updated {formatDate(item.updated_at)}</span><Button variant="ghost" size="small" aria-label="Delete note" onClick={() => deleteNote.mutate(item.id)}><Trash2 size={15} />Delete</Button></div></div>)}
              {!(app.notes ?? []).length ? <p className="muted">No notes yet.</p> : null}
            </div>
          </Card>
        </div>
        <aside className="detail-aside">
          <Card className="sticky-actions cx-application-side">
            <h2>Keep it current</h2>
            <p className="muted">Update the stage when something changes so ApplyAI can keep the right next steps visible.</p>
            <Field label="Application stage" htmlFor="application-status"><NativeSelect id="application-status" value={app.current_status} disabled={statusMutation.isPending} onChange={(event) => statusMutation.mutate(event.target.value)}>{statuses.map((status) => <option value={status} key={status}>{titleCase(status)}</option>)}</NativeSelect></Field>
            <form
              className="form-stack"
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                trackerMutation.mutate({
                  deadline_at: toIsoOrNull(form.get("deadline_at")),
                  interview_at: toIsoOrNull(form.get("interview_at")),
                  next_action_at: toIsoOrNull(form.get("next_action_at")),
                  offer_minimum: toNumberOrNull(form.get("offer_minimum")),
                  offer_maximum: toNumberOrNull(form.get("offer_maximum")),
                  offer_currency: String(form.get("offer_currency") || "USD").toUpperCase(),
                  offer_notes: String(form.get("offer_notes") || "").trim() || null,
                  source_channel: String(form.get("source_channel") || "").trim() || null,
                  priority: String(form.get("priority") || "MEDIUM") as "LOW" | "MEDIUM" | "HIGH",
                });
              }}
            >
              <Field label="Priority" htmlFor="tracker-priority">
                <NativeSelect id="tracker-priority" name="priority" defaultValue={app.tracker?.priority ?? "MEDIUM"}>
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                </NativeSelect>
              </Field>
              <Field label="Source" htmlFor="tracker-source">
                <Input id="tracker-source" name="source_channel" defaultValue={app.tracker?.source_channel ?? ""} placeholder="Referral, company site, recruiter…" />
              </Field>
              <Field label="Next action" htmlFor="tracker-next-action">
                <Input id="tracker-next-action" name="next_action_at" type="datetime-local" defaultValue={localDateTimeValue(app.tracker?.next_action_at)} />
              </Field>
              <Field label="Interview" htmlFor="tracker-interview">
                <Input id="tracker-interview" name="interview_at" type="datetime-local" defaultValue={localDateTimeValue(app.tracker?.interview_at)} />
              </Field>
              <Field label="Application deadline" htmlFor="tracker-deadline">
                <Input id="tracker-deadline" name="deadline_at" type="datetime-local" defaultValue={localDateTimeValue(app.tracker?.deadline_at)} />
              </Field>
              <div className="form-grid two">
                <Field label="Offer minimum" htmlFor="tracker-offer-min">
                  <Input id="tracker-offer-min" name="offer_minimum" inputMode="numeric" defaultValue={app.tracker?.offer_minimum ?? ""} />
                </Field>
                <Field label="Offer maximum" htmlFor="tracker-offer-max">
                  <Input id="tracker-offer-max" name="offer_maximum" inputMode="numeric" defaultValue={app.tracker?.offer_maximum ?? ""} />
                </Field>
              </div>
              <Field label="Offer currency" htmlFor="tracker-offer-currency">
                <Input id="tracker-offer-currency" name="offer_currency" maxLength={3} defaultValue={app.tracker?.offer_currency ?? "USD"} />
              </Field>
              <Field label="Offer notes" htmlFor="tracker-offer-notes">
                <Textarea id="tracker-offer-notes" name="offer_notes" defaultValue={app.tracker?.offer_notes ?? ""} placeholder="Equity, bonus, benefits, negotiation notes…" />
              </Field>
              <Button type="submit" size="small" disabled={trackerMutation.isPending}>
                {trackerMutation.isPending ? "Saving…" : "Save opportunity details"}
              </Button>
            </form>
            <div className="facts-list">
              <div className="fact-row"><CalendarDays size={17} /><div><strong>Started</strong><span>{formatDate(app.created_at)}</span></div></div>
              <div className="fact-row"><CalendarDays size={17} /><div><strong>Last updated</strong><span>{formatDate(app.updated_at)}</span></div></div>
            </div>
            <div className="button-row"><Link className="ui-button ui-button-secondary ui-button-small" href={`/interview/${posting.id}`}>Interview prep</Link><Link className="ui-button ui-button-secondary ui-button-small" href="/network">Recruiter contacts</Link></div>
            <Link className="ui-button ui-button-secondary ui-button-small" href={shareHref}><Share2 size={15} />Create private Resume Share</Link>
            <p className="muted" style={{ fontSize: 12, lineHeight: 1.5 }}>Resume Share reports anonymous engagement signals only. It does not identify viewers or infer their company.</p>
          </Card>
        </aside>
      </div>
    </>
  );
}
