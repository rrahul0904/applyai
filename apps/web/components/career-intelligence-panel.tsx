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
    label: "Review fit",
    description: "See the strengths and gaps that matter most for this role.",
    icon: BrainCircuit,
  },
  {
    task: "resume-tailoring",
    label: "Tailor resume",
    description: "Focus your resume on relevant experience you can support.",
    icon: FilePenLine,
  },
  {
    task: "application-copilot",
    label: "Prepare application",
    description: "Draft cover-letter and application material for your review.",
    icon: Sparkles,
  },
  {
    task: "interview-prep",
    label: "Practice interview",
    description: "Prepare role-specific questions and answer outlines from your experience.",
    icon: MessageSquareText,
  },
];

const artifactTitle: Record<string, string> = {
  DEEP_MATCH: "Role fit",
  RESUME_TAILORING: "Tailored resume",
  APPLICATION_COPILOT: "Application preparation",
  INTERVIEW_PREP: "Interview preparation",
};

function textList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function matchDecisionLabel(value: string) {
  switch (value.toUpperCase()) {
    case "PRIORITIZE":
      return "Strong fit";
    case "CONSIDER":
      return "Worth considering";
    case "DEPRIORITIZE":
      return "Lower priority";
    case "SKIP":
      return "Not recommended";
    default:
      return titleCase(value);
  }
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
  const evidenceCount = Array.isArray(artifact.evidence.refs) ? artifact.evidence.refs.length : 0;

  return (
    <div className={styles.artifact}>
      <div className={styles.artifactHeader}>
        <div>
          <p className="eyebrow">
            {artifactTitle[artifact.artifact_type] ?? titleCase(artifact.artifact_type)}
          </p>
          <strong>Ready to review</strong>
        </div>
        <Badge tone={artifact.candidate_verified ? "success" : "warning"}>
          {artifact.candidate_verified ? "Reviewed" : "Needs review"}
        </Badge>
      </div>
      {summary ? <p className={styles.description}>{summary}</p> : null}
      {strengths.length ? (
        <div>
          <strong>What lines up well</strong>
          <ul>
            {strengths.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      ) : null}
      {gaps.length ? (
        <div>
          <strong>What to think through</strong>
          <ul>
            {gaps.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      ) : null}
      {questions.length ? (
        <p className={styles.muted}>{questions.length} interview questions prepared.</p>
      ) : null}
      <p className={styles.muted}>
        Based on {evidenceCount} verified {evidenceCount === 1 ? "fact" : "facts"} from your career profile.
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
      toast.success("Your preparation is ready to review.");
    } else {
      toast.error("We couldn't complete that preparation. Please try again.");
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
        toast.success("Your preparation is ready to review.");
      } else {
        setActiveRunId(result.id);
        toast.message("Preparing this for you…");
      }
    },
    onError: () => toast.error("We couldn't start that preparation."),
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
          <p className="eyebrow">Why this role might fit</p>
          <h2>Understand the fit, then prepare with confidence.</h2>
          <p className={styles.description}>
            Use your verified experience to compare the role, strengthen your resume, prepare application material, and practice for interviews. Nothing is submitted without you.
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
              {matchDecisionLabel(match.data.decision)}
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
          <strong>{currentRun.status === "FAILED" ? "Needs attention" : "Working on it"}</strong>
          <span>
            {currentRun.status === "FAILED"
              ? currentRun.error_code ?? "Preparation failed"
              : "Using your verified experience to prepare this step."}
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
              Try again
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
          Choose a step above when you are ready. ApplyAI will keep the result attached to this role for you to review.
        </p>
      )}
    </Card>
  );
}
