"use client";

import { useMutation } from "@tanstack/react-query";
import { ExternalLink, Send } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { platformApi } from "@/lib/api/platform-client";
import { Badge, Button, Card } from "@/components/ui";

export function ApplicationSubmissionPanel({ applicationId, jobId, sourceUrl }: { applicationId: string; jobId: string; sourceUrl?: string | null }) {
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const firstParty = useMutation({
    mutationFn: async () => {
      const draft = await platformApi.submissions.create({ application_id: applicationId, mode: "FIRST_PARTY", provider: "APPLYAI", payload: { candidate_reviewed: true } });
      const id = String(draft.id);
      await platformApi.submissions.approve(id);
      return platformApi.submissions.execute(id);
    },
    onSuccess: (data) => { setState(data); toast.success("Application submitted through ApplyAI"); },
    onError: () => toast.error("This employer does not accept first-party ApplyAI submission for this role."),
  });
  const handoff = useMutation({
    mutationFn: async () => {
      if (!sourceUrl) throw new Error("No employer application URL is available");
      const draft = await platformApi.submissions.create({ application_id: applicationId, mode: "EXTERNAL_HANDOFF", provider: "MANUAL", target_url: sourceUrl, payload: { candidate_reviewed: true } });
      const id = String(draft.id);
      await platformApi.submissions.approve(id);
      return platformApi.submissions.execute(id);
    },
    onSuccess: (data) => { setState(data); const url = typeof data.target_url === "string" ? data.target_url : null; if (url) window.open(url, "_blank", "noopener,noreferrer"); },
    onError: (error) => toast.error(error.message),
  });

  return <Card className="detail-section">
    <div className="section-header"><div><h2>Application submission</h2><p>ApplyAI never submits without your explicit approval.</p></div>{state?.status ? <Badge tone={state.status === "SUBMITTED" ? "success" : "info"}>{String(state.status)}</Badge> : null}</div>
    <p className="muted">First-party employers can receive the reviewed package directly. Other employers open their verified application page after ApplyAI prepares and records the handoff.</p>
    <div className="button-row"><Button disabled={firstParty.isPending} onClick={() => firstParty.mutate()}><Send size={16}/>Submit through ApplyAI</Button>{sourceUrl ? <Button variant="secondary" disabled={handoff.isPending} onClick={() => handoff.mutate()}><ExternalLink size={16}/>Continue on employer site</Button> : null}</div>
    <div className="button-row"><Link href={`/resume/studio?jobId=${jobId}`} className="ui-button ui-button-ghost ui-button-small">Resume Studio</Link><Link href={`/interview/${jobId}`} className="ui-button ui-button-ghost ui-button-small">Interview Copilot</Link></div>
  </Card>;
}
