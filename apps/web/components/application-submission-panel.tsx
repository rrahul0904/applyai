"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, Send, ShieldCheck } from "lucide-react";
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
    onError: () => toast.error("This employer does not accept direct ApplyAI submission for this role."),
  });
  const handoff = useMutation({
    mutationFn: async () => {
      if (!sourceUrl) throw new Error("No employer application URL is available");
      const draft = await platformApi.submissions.create({ application_id: applicationId, mode: "EXTERNAL_HANDOFF", provider: "MANUAL", target_url: sourceUrl, payload: { candidate_reviewed: true } });
      const id = String(draft.id);
      await platformApi.submissions.approve(id);
      return platformApi.submissions.execute(id);
    },
    onSuccess: (data) => {
      setState(data);
      const url = typeof data.target_url === "string" ? data.target_url : null;
      if (url) window.open(url, "_blank", "noopener,noreferrer");
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <Card className="detail-section cx-submit-card">
      <div className="section-header">
        <div>
          <p className="eyebrow">Final step</p>
          <h2>Review, then apply</h2>
          <p>Nothing is sent until you choose how to continue.</p>
        </div>
        {state?.status ? <Badge tone={state.status === "SUBMITTED" ? "success" : "info"}>{String(state.status)}</Badge> : null}
      </div>

      <div className="cx-submit-confidence">
        <div><CheckCircle2 size={16} /><span>Your application stays attached to this role</span></div>
        <div><ShieldCheck size={16} /><span>You stay in control of the final submission</span></div>
      </div>

      <div className="button-row cx-submit-actions">
        <Button disabled={firstParty.isPending} onClick={() => firstParty.mutate()}><Send size={16}/>{firstParty.isPending ? "Submitting…" : "Submit with ApplyAI"}</Button>
        {sourceUrl ? <Button variant="secondary" disabled={handoff.isPending} onClick={() => handoff.mutate()}><ExternalLink size={16}/>{handoff.isPending ? "Opening…" : "Continue on employer site"}</Button> : null}
      </div>
      <div className="cx-inline-tools">
        <Link href={`/resume/studio?jobId=${jobId}`}>Review resume</Link>
        <Link href={`/interview/${jobId}`}>Prepare for interview</Link>
      </div>
    </Card>
  );
}
