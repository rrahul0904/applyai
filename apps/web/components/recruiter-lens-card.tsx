"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  MessageCircleQuestion,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";

import { Badge, Button } from "@/components/ui";
import { recruiterLensApi } from "@/lib/api/recruiter-lens";
import { titleCase } from "@/lib/utils";
import styles from "./recruiter-lens-card.module.css";

function criterionTone(status: "SUPPORTED" | "PARTIAL" | "NOT_EVIDENCED") {
  if (status === "SUPPORTED") return "success" as const;
  if (status === "PARTIAL") return "warning" as const;
  return undefined;
}

export function RecruiterLensCard({ jobId }: { jobId: string }) {
  const [showAllCriteria, setShowAllCriteria] = useState(false);
  const lens = useQuery({
    queryKey: ["recruiter-lens", jobId],
    queryFn: ({ signal }) => recruiterLensApi.get(jobId, signal),
  });

  if (lens.isLoading) {
    return (
      <section className={styles.card} aria-label="Recruiter Lens" aria-busy="true">
        <p className={styles.loading}>Building your evidence-based Recruiter Lens…</p>
      </section>
    );
  }

  if (lens.isError || !lens.data) {
    return (
      <section className={styles.card} aria-label="Recruiter Lens">
        <p className={styles.error} role="alert">
          {lens.error instanceof Error
            ? lens.error.message
            : "Recruiter Lens is unavailable for this role. You can still review the job and your saved evidence."}
        </p>
      </section>
    );
  }

  const item = lens.data;
  const visibleCriteria = showAllCriteria ? item.criteria : item.criteria.slice(0, 3);
  const hiddenCriteriaCount = Math.max(0, item.criteria.length - visibleCriteria.length);
  const preparationSummary =
    item.counts.not_evidenced > 0
      ? `${item.counts.supported} supported, ${item.counts.partial} partial, and ${item.counts.not_evidenced} not yet evidenced. Start with the gaps that matter most for this role.`
      : item.counts.partial > 0
        ? `${item.counts.supported} supported and ${item.counts.partial} partially evidenced. Strengthen the partial areas before you rely on them.`
        : `Your saved evidence supports all ${item.counts.supported} criteria surfaced for this role.`;

  return (
    <section className={styles.card} aria-labelledby="recruiter-lens-title">
      <div className={styles.header}>
        <div className={styles.title}>
          <ScanSearch size={21} aria-hidden="true" />
          <div>
            <h3 id="recruiter-lens-title">Recruiter Lens</h3>
            <p>
              A candidate-side screening mirror: what your verified evidence makes obvious,
              what still looks thin, and where an interviewer may dig deeper.
            </p>
          </div>
        </div>
        <div className={styles.tier} aria-label={`Recruiter Lens tier ${item.tier}`}>
          <strong>{item.tier}</strong>
          <span>readiness tier</span>
        </div>
      </div>

      <div className={styles.summaryStrip} aria-label="Recruiter Lens summary">
        <CheckCircle2 size={18} aria-hidden="true" />
        <div>
          <strong>What matters first</strong>
          <p>{preparationSummary}</p>
        </div>
      </div>

      <div className={styles.metrics}>
        <div className={styles.metric} data-evidence-state="score">
          <strong>{item.score}%</strong>
          <span>screening readiness</span>
        </div>
        <div className={styles.metric} data-evidence-state="supported">
          <strong>{item.counts.supported}</strong>
          <span>supported</span>
        </div>
        <div className={styles.metric} data-evidence-state="partial">
          <strong>{item.counts.partial}</strong>
          <span>partial evidence</span>
        </div>
        <div className={styles.metric} data-evidence-state="missing">
          <strong>{item.counts.not_evidenced}</strong>
          <span>not evidenced</span>
        </div>
      </div>

      <div className={styles.block}>
        <div className={styles.blockHeader}>
          <div>
            <h4>Evidence that shapes this screening view</h4>
            <p>Start with the first three criteria; expand only when you need the full detail.</p>
          </div>
          <Badge>{titleCase(item.confidence)} confidence</Badge>
        </div>
        <div className={styles.criteria} id="recruiter-lens-criteria">
          {visibleCriteria.map((criterion) => (
            <div className={styles.criterion} key={criterion.id}>
              <strong>{criterion.label}</strong>
              <Badge tone={criterionTone(criterion.status)}>
                {titleCase(criterion.status)}
              </Badge>
              {criterion.evidence ? (
                <p>Evidence: {criterion.evidence.snippet}</p>
              ) : (
                <p>No explicit verified evidence found in your saved profile.</p>
              )}
            </div>
          ))}
        </div>
        {item.criteria.length > 3 ? (
          <Button
            type="button"
            variant="ghost"
            className={styles.disclosureButton}
            aria-expanded={showAllCriteria}
            aria-controls="recruiter-lens-criteria"
            onClick={() => setShowAllCriteria((current) => !current)}
          >
            <ChevronDown
              size={16}
              aria-hidden="true"
              className={showAllCriteria ? styles.chevronOpen : undefined}
            />
            {showAllCriteria
              ? "Show less screening detail"
              : `Show ${hiddenCriteriaCount} more criteria`}
          </Button>
        ) : null}
      </div>

      <div className={styles.insightGrid}>
        <details className={`${styles.block} ${styles.insightDisclosure}`}>
          <summary className={styles.insightSummary}>
            <span><AlertTriangle size={16} aria-hidden="true" />Potential concerns</span>
            <Badge tone={item.concerns.length ? "warning" : "success"}>{item.concerns.length}</Badge>
          </summary>
          {item.concerns.length ? (
            <div className={styles.concerns}>
              {item.concerns.slice(0, 4).map((concern) => (
                <div className={styles.concern} key={`${concern.criterion_id}-${concern.message}`}>
                  <AlertTriangle size={16} aria-hidden="true" />
                  <p>{concern.message}</p>
                </div>
              ))}
            </div>
          ) : <p className={styles.clearState}>No additional evidence concerns surfaced.</p>}
        </details>

        <details className={`${styles.block} ${styles.insightDisclosure}`}>
          <summary className={styles.insightSummary}>
            <span><MessageCircleQuestion size={16} aria-hidden="true" />Questions to prepare for</span>
            <Badge>{item.interview_questions.length}</Badge>
          </summary>
          {item.interview_questions.length ? (
            <div className={styles.questions}>
              {item.interview_questions.slice(0, 4).map((question) => (
                <div className={styles.question} key={`${question.criterion_id}-${question.question}`}>
                  <MessageCircleQuestion size={16} aria-hidden="true" />
                  <p>{question.question}</p>
                </div>
              ))}
            </div>
          ) : <p className={styles.clearState}>No gap-driven questions are needed from this evidence set.</p>}
        </details>
      </div>

      <p className={styles.disclaimer}>
        <ShieldCheck size={16} aria-hidden="true" />
        <span>{item.disclaimer}</span>
      </p>
    </section>
  );
}
