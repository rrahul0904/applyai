"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileText, Plus, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, EmptyState, Field, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { platformApi, type ResumeDocument } from "@/lib/api/platform-client";

function resumeText(document: ResumeDocument | null) {
  const content = document?.content ?? {};
  return typeof content.summary === "string" ? content.summary : "";
}

export function CandidateResumeStudioView() {
  const queryClient = useQueryClient();
  const docs = useQuery({ queryKey: ["resume-studio"], queryFn: platformApi.resumeStudio.list });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = useMemo(() => docs.data?.find((item) => item.id === selectedId) ?? docs.data?.[0] ?? null, [docs.data, selectedId]);
  const [draftSummary, setDraftSummary] = useState("");

  const create = useMutation({
    mutationFn: () => platformApi.resumeStudio.create({ title: "New resume", content: { summary: "", sections: [] } }),
    onSuccess: async (item) => {
      setSelectedId(item.id);
      setDraftSummary("");
      await queryClient.invalidateQueries({ queryKey: ["resume-studio"] });
      toast.success("Resume created");
    },
  });
  const save = useMutation({
    mutationFn: async () => {
      if (!selected) return;
      return platformApi.resumeStudio.update(selected.id, { content: { ...selected.content, summary: draftSummary || resumeText(selected) }, status: "REVIEWED" });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["resume-studio"] });
      toast.success("Resume saved");
    },
  });
  const exportDoc = useMutation({
    mutationFn: async () => selected ? platformApi.resumeStudio.export(selected.id, "txt") : null,
    onSuccess: (file) => {
      if (!file) return;
      const blob = new Blob([file.content], { type: file.content_type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.filename;
      anchor.click();
      URL.revokeObjectURL(url);
    },
  });

  if (docs.isLoading) return <Skeleton className="page-skeleton" />;

  return (
    <>
      <PageHeader
        eyebrow="Resume"
        title="A strong resume, grounded in what you've actually done."
        description="Create job-specific versions, review every change, and keep your verified experience in control."
        action={<Button onClick={() => create.mutate()} disabled={create.isPending}><Plus size={16}/>New resume</Button>}
      />

      <div className="cx-resume-layout">
        <aside className="cx-resume-list">
          <div className="cx-section-heading compact"><div><p className="eyebrow">Your resumes</p><h2>Versions</h2></div></div>
          {(docs.data ?? []).length ? (docs.data ?? []).map((item) => (
            <button
              type="button"
              key={item.id}
              className={selected?.id === item.id ? "cx-resume-item active" : "cx-resume-item"}
              onClick={() => { setSelectedId(item.id); setDraftSummary(""); }}
            >
              <FileText size={17} />
              <span><strong>{item.title}</strong><small>Updated version {item.version}</small></span>
              {item.status === "FINAL" ? <Badge tone="success">Ready</Badge> : null}
            </button>
          )) : <p className="muted">Create your first resume to get started.</p>}
        </aside>

        <div className="cx-resume-main">
          {selected ? (
            <Card className="cx-resume-editor">
              <div className="cx-section-heading">
                <div><p className="eyebrow">Editing</p><h2>{selected.title}</h2></div>
                <Badge tone={selected.status === "FINAL" ? "success" : "info"}>{selected.status === "FINAL" ? "Ready" : "In progress"}</Badge>
              </div>
              <Field label="Professional summary" htmlFor="resume-summary">
                <Textarea id="resume-summary" value={draftSummary || resumeText(selected)} onChange={(event) => setDraftSummary(event.target.value)} rows={11} />
              </Field>

              <div className="cx-resume-safety">
                <div><ShieldCheck size={17} /><span>ApplyAI keeps your source experience separate from generated wording.</span></div>
                <div><CheckCircle2 size={17} /><span>Review changes before you use this resume anywhere.</span></div>
              </div>

              <div className="button-row">
                <Button onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "Saving…" : "Save changes"}</Button>
                <Button variant="secondary" onClick={() => exportDoc.mutate()} disabled={exportDoc.isPending}><Download size={16}/>Download</Button>
              </div>
            </Card>
          ) : (
            <Card><EmptyState icon={<FileText size={22} />} title="Create your first resume" description="Start with a clean version, then tailor it as strong opportunities come in." action={<Button onClick={() => create.mutate()}>Create resume</Button>} /></Card>
          )}
        </div>
      </div>
    </>
  );
}
