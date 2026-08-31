"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Share2, Upload } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";
import { formatDate, titleCase } from "@/lib/utils";

function statusTone(status: string): "neutral" | "success" | "warning" | "info" | "danger" {
  if (status === "COMPLETED") return "success";
  if (status === "FAILED") return "danger";
  if (status === "NEEDS_REVIEW") return "warning";
  return "info";
}

export function ResumeView() {
  const queryClient = useQueryClient();
  const resumes = useQuery({
    queryKey: ["resumes"],
    queryFn: ({ signal }) => api.resumes.list(signal),
    refetchInterval: 2000,
  });
  const upload = useMutation({
    mutationFn: (file: File) => api.resumes.upload(file),
    onSuccess: async () => {
      toast.success("Resume uploaded");
      await queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <>
      <PageHeader
        eyebrow="Resume"
        title="Manage the documents behind your profile."
        description="PDF and DOCX files are private. Extraction remains reviewable before it changes your candidate profile."
        action={
          <div className="button-row">
            <Link className="ui-button ui-button-secondary" href="/resume/signals"><Share2 size={17} />Share & track</Link>
            <label className="ui-button ui-button-primary"><Upload size={17} />Upload resume<input className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => { const file = event.target.files?.[0]; if (file) upload.mutate(file); }} /></label>
          </div>
        }
      />
      {resumes.isError ? <ErrorState message={resumes.error.message} retry={() => resumes.refetch()} /> : resumes.isLoading ? (
        <div className="list-stack">{[1, 2].map((item) => <Skeleton className="skeleton-row" key={item} />)}</div>
      ) : resumes.data?.length ? (
        <div className="list-stack">
          {resumes.data.map((resume) => <Card className="profile-card" key={resume.id}>
            <div className="section-header"><div><h2>{resume.filename}</h2><p>Uploaded {formatDate(resume.created_at)} · {(resume.file_size / 1024).toFixed(0)} KB</p></div><Badge tone={statusTone(resume.processing_status)}>{titleCase(resume.processing_status)}</Badge></div>
            {resume.processing_status === "NEEDS_REVIEW" ? <div className="button-row"><Link className="ui-button ui-button-secondary ui-button-small" href="/onboarding">Review extracted profile</Link></div> : null}
            {resume.processing_status === "FAILED" ? <p className="field-error">We couldn&apos;t read this file completely. Upload another version or continue editing your profile manually.</p> : null}
          </Card>)}
        </div>
      ) : (
        <Card><EmptyState icon={<FileText size={22} />} title="No resume uploaded" description="Upload a PDF or DOCX to build your profile faster." action={<Button onClick={() => document.querySelector<HTMLInputElement>('input[type="file"]')?.click()}>Choose a resume</Button>} /></Card>
      )}
    </>
  );
}
