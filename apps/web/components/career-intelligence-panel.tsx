"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, FilePenLine, MessageSquareText, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  api,
  type AIArtifact,
  type AIJobRun,
  type CareerTaskPath,
} from "@/lib/api/client";
import { Badge, Button, Card } from "@/components/ui";
import { titleCase } from "@/lib/utils";

const actions: Array<{
  task: CareerTaskPath;
  label: string;
  description: string;
  icon: typeof BrainCircuit;
}> = [
  {
    task: "deep-match",
    label: "Analyze fit",
    description: "Combine the explainable baseline with evidence-grounded career intelligence.",
    icon: BrainCircuit,
  },
  {
    task: "resume-tailoring",
    label: "Tailor resume",
    description: "Create evidence-locked suggestions that require your review.",
    icon: FilePenLine,
  },
  {
    task: "application-copilot",
    label: "Prepare application",
    description: "Draft reviewable cover-letter, answer, and recruiter-outreach material.",
    icon: Sparkles,
  },
  {
    task: "interview-prep",
    label: "Prepare interview",
    description: "Build role-specific questions and answer outlines from verified evidence.",
    icon: MessageSquareText,
  },
];

const artifactTitle: Record<string, string> = {
  DEEP_MATCH: "Fit analysis",
  RESUME_TAILORING: "Resume tailoring",
  APPLICATION_COPILOT: "Application copilot",
  INTERVIEW_PREP: "Interview preparation",
};

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function ArtifactPreview({ artifact }: { artifact: AIArtifact }) {
  const content = artifact.content;
  const summary =
    (typeof content.summary === "string" && content.summary) ||
    (typeof content.strategy_summary === "string" && content.strategy_summary) ||
    null;
  const strengths = textList(content.strengths);
  const gaps = textList(content.gaps);
  const questions = Array.isArray(content.likely_questions) ? content.likely_questions : [];

  return (
    <div className="career-artifact">
      <div className="detail-title-row">
        <div>
          <p className="eyebrow">{artifactTitle[artifact.artifact_type] ?? titleCase(artifact.artifact_type)}</p>
          <strong>Version {artifact.version}</strong>
        </div>
        <Badge tone={artifact.candidate_verified ? "success" : "warning"}>
          {artifact.candidate_verified ? "Verified" : "Review required"}
        </Badge>
      </div>
      {summary ? <p className="detail-copy">{summary}</p> : null}
      {strengths.length ? (
        <div>
          <strong>Strengths</strong>
          <ul>{strengths.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      ) : null}
      {gaps.length ? (
        <div>
          <strong>Gaps to review</strong>
          <ul>{gaps.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      ) : null}
      {questions.length ? <p className="muted-copy">{questions.length} interview questions prepared.</p> : null}
      <p className="muted-copy">Grounded in {Array.isArray(artifact.evidence.refs) ? artifact.evidence.refs.length : 0} verified evidence references.</p>
    </div>
  );
}

export function CareerIntelligencePanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<AIJobRun | null>(null);

  const artifacts = useQuery({
    queryKey: ["career-v2-artifacts", jobId],
    queryFn: ({ signal }) => api.careerV2.artifacts(jobId, signal),
  });

  const deepMatchExists = useMemo(
    () => artifacts.data?.items.some((item) => item.artifact_type === "DEEP_MATCH") ?? false,
    [artifacts.data],
  );

  const match = useQuery({
    queryKey: ["career-v2-match", jobId],
    queryFn: ({ signal }) => api.careerV2.match(jobId, signal),
    enabled: deepMatchExists,
    retry: false,
  });

  const run = useQuery({
    queryKey: ["career-v2-run", activeRunId],
    queryFn: ({ signal }) => api.careerV2.run(activeRunId as string, signal),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "QUEUED" || status === "PROCESSING" ? 1500 : false;
    },
  });

  useEffect(() => {
    if (!run.data) return;
    setLastRun(run.data);
    if (run.data.status === "COMPLETED") {
      setActiveRunId(null);
      queryClient.invalidateQueries({ queryKey: ["career-v2-artifacts", jobId] });
      queryClient.invalidateQueries({ queryKey: ["career-v2-match", jobId] });
      toast.success("Career intelligence is ready for review.");
    } else if (run.data.status === "FAILED") {
      setActiveRunId(null);
      toast.error("Career intelligence could not complete this request.");
    }
  }, [jobId, queryClient, run.data]);

  const createRun = useMutation({
    mutationFn: ({ task }: { task: CareerTaskPath }) => api.careerV2.start(jobId, task),
    onSuccess: (result) => {
      setLastRun(result);
      if (result.status === "COMPLETED") {
        queryClient.invalidateQueries({ queryKey: ["career-v2-artifacts", jobId] });
        queryClient.invalidateQueries({ queryKey: ["career-v2-match", jobId] });
        toast.success("Career intelligence is ready for review.");
      } else {
        setActiveRunId(result.id);
        toast.message("Career intelligence request queued.");
      }
    },
    onError: () => toast.error("We couldn't start this career intelligence request."),
  });

  const latestArtifacts = useMemo(() => {
    const seen = new Set<string>();
    return (artifacts.data?.items ?? []).filter((item) => {
      if (seen.has(item.artifact_type)) return false;
      seen.add(item.artifact_type);
      return true;
    });
  }, [artifacts.data]);

  const busy = createRun.isPending || Boolean(activeRunId);

  return (
    <Card className="detail-section career-intelligence-panel">
      <div className="detail-title-row">
        <div>
          <p className="eyebrow">Career Intelligence V2</p>
          <h2>Turn this job into an evidence-backed plan</h2>
          <p className="detail-copy">
            ApplyAI uses your verified profile, career memory, and job evidence. Suggestions never represent a hiring probability or an external application submission.
          </p>
        </div>
        {match.data ? (
          <div className="career-score" aria-label={`${match.data.final_score} percent match score`}>
            <strong>{match.data.final_score}</strong>
            <span>/100</span>
            <Badge tone={match.data.decision === "PRIORITIZE" ? "success" : "info"}>
              {titleCase(match.data.decision)}
            </Badge>
          </div>
        ) : null}
      </div>

      <div className="career-action-grid">
        {actions.map(({ task, label, description, icon: Icon }) => (
          <button
            className="career-action-card"
            key={task}
            type="button"
            disabled={busy}
            onClick={() => createRun.mutate({ task })}
          >
            <Icon size={20} aria-hidden="true" />
            <span><strong>{label}</strong><small>{description}</small></span>
          </button>
        ))}
      </div>

      {lastRun && lastRun.status !== "COMPLETED" ? (
        <div className="career-run-status" role="status">
          <span className="status-dot" aria-hidden="true" />
          <strong>{titleCase(lastRun.status)}</strong>
          <span>{lastRun.status === "FAILED" ? lastRun.error_code ?? "Request failed" : "Your evidence is being processed."}</span>
          {lastRun.status === "FAILED" ? (
            <Button
              size="small"
              variant="secondary"
              onClick={async () => {
                const retried = await api.careerV2.retry(lastRun.id);
                setLastRun(retried);
                if (retried.status !== "COMPLETED") setActiveRunId(retried.id);
              }}
            >
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {latestArtifacts.length ? (
        <div className="career-artifact-list">
          {latestArtifacts.map((artifact) => <ArtifactPreview artifact={artifact} key={artifact.id} />)}
        </div>
      ) : (
        <p className="muted-copy">No AI artifacts yet. Start with Analyze fit to create the hybrid match baseline.</p>
      )}
    </Card>
  );
}
