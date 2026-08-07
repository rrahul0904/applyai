"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, FilePenLine, MessageSquareText, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card } from "@/components/ui";
import {
  api,
  type AIArtifact,
  type AIJobRun,
  type CareerTaskPath,
} from "@/lib/api/client";
import { titleCase } from "@/lib/utils";
import styles from "./career-intelligence-panel.module.css";

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
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function ArtifactPreview({ artifact }: { artifact: AIArtifact }) {
  const content = artifact.content;
  const summary =
    (typeof content.summary === "string" && content.summary) ||
    (typeof content.strategy_summary === "string" && content.strategy_summary) ||
    null;
  const strengths = textList(content.strengths);
  const gaps = textList(content.gaps);
  const questions = Array.isArray(content.likely_questions)
    ? content.likely_questions
    : [];

  return (
    <div className={styles.artifact}>
      <div className={styles.artifactHeader}>
        <div>
          <p className="eyebrow">
            {artifactTitle[artifact.artifact_type] ?? titleCase(artifact.artifact_type)}
          </p>
          <strong>Version {artifact.version}</strong>
        </div>
        <Badge tone={artifact.candidate_verified ? "success" : "warning"}>
          {artifact.candidate_verified ? "Verified" : "Review required"}
        </Badge>
      </div>
      {summary ? <p className={styles.description}>{summary}</p> : null}
      {strengths.length ? (
        <div>
          <strong>Strengths</strong>
          <ul>
            {strengths.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      ) : null}
      {gaps.length ? (
        <div>
          <strong>Gaps to review</strong>
          <ul>
            {gaps.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      ) : null}
      {questions.length ? (
        <p className={styles.muted}>{questions.length} interview questions prepared.</p>
      ) : null}
      <p className={styles.muted}>
        Grounded in {Array.isArray(artifact.evidence.refs) ? artifact.evidence.refs.length : 0} verified evidence references.
      </p>
    </div>
  );
}

export function CareerIntelligencePanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [submittedRun, setSubmittedRun] = useState<AIJobRun | null>(null);
  const handledTerminalRun = useRef<string | null>(null);

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
      const runStatus = query.state.data?.status;
      return runStatus === "QUEUED" || runStatus === "PROCESSING" ? 1500 : false;
    },
  });

  useEffect(() => {
    const result = run.data;
    if (!result || (result.status !== "COMPLETED" && result.status !== "FAILED")) return;

    const terminalKey = `${result.id}:${result.status}:${result.attempt_count}`;
    if (handledTerminalRun.current === terminalKey) return;
    handledTerminalRun.current = terminalKey;

    if (result.status === "COMPLETED") {
      queryClient.invalidateQueries({ queryKey: ["career-v2-artifacts", jobId] });
      queryClient.invalidateQueries({ queryKey: ["career-v2-match", jobId] });
      toast.success("Career intelligence is ready for review.");
    } else {
      toast.error("Career intelligence could not complete this request.");
    }
  }, [jobId, queryClient, run.data]);

  const createRun = useMutation({
    mutationFn: ({ task }: { task: CareerTaskPath }) => api.careerV2.start(jobId, task),
    onSuccess: (result) => {
      handledTerminalRun.current = null;
      setSubmittedRun(result);
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

  const currentRun = run.data?.id === activeRunId ? run.data : submittedRun;
  const busy =
    createRun.isPending ||
    currentRun?.status === "QUEUED" ||
    currentRun?.status === "PROCESSING";

  return (
    <Card className={`detail-section ${styles.panel}`}>
      <div className={styles.header}>
        <div>
          <p className="eyebrow">Career Intelligence V2</p>
          <h2>Turn this job into an evidence-backed plan</h2>
          <p className={styles.description}>
            ApplyAI uses your verified profile, career memory, and job evidence. Suggestions never represent a hiring probability or an external application submission.
          </p>
        </div>
        {match.data ? (
          <div
            className={styles.score}
            aria-label={`${match.data.final_score} percent match score`}
          >
            <strong>{match.data.final_score}</strong>
            <span>/100</span>
            <Badge tone={match.data.decision === "PRIORITIZE" ? "success" : "info"}>
              {titleCase(match.data.decision)}
            </Badge>
          </div>
        ) : null}
      </div>

      <div className={styles.actionGrid}>
        {actions.map(({ task, label, description, icon: Icon }) => (
          <button
            className={styles.actionCard}
            key={task}
            type="button"
            disabled={busy}
            onClick={() => createRun.mutate({ task })}
          >
            <Icon size={20} aria-hidden="true" />
            <span>
              <strong>{label}</strong>
              <small>{description}</small>
            </span>
          </button>
        ))}
      </div>

      {currentRun && currentRun.status !== "COMPLETED" ? (
        <div className={styles.runStatus} role="status">
          <span className={styles.dot} aria-hidden="true" />
          <strong>{titleCase(currentRun.status)}</strong>
          <span>
            {currentRun.status === "FAILED"
              ? currentRun.error_code ?? "Request failed"
              : "Your evidence is being processed."}
          </span>
          {currentRun.status === "FAILED" ? (
            <Button
              size="small"
              variant="secondary"
              onClick={async () => {
                const retried = await api.careerV2.retry(currentRun.id);
                handledTerminalRun.current = null;
                setSubmittedRun(retried);
                if (retried.status !== "COMPLETED") setActiveRunId(retried.id);
              }}
            >
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {latestArtifacts.length ? (
        <div className={styles.artifactList}>
          {latestArtifacts.map((artifact) => (
            <ArtifactPreview artifact={artifact} key={artifact.id} />
          ))}
        </div>
      ) : (
        <p className={styles.muted}>
          No AI artifacts yet. Start with Analyze fit to create the hybrid match baseline.
        </p>
      )}
    </Card>
  );
}
