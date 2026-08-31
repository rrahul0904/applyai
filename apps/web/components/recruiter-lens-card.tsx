"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  MessageCircleQuestion,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/ui";
import { recruiterLensApi } from "@/lib/api/recruiter-lens";
import { titleCase } from "@/lib/utils";
import styles from "./recruiter-lens-card.module.css";

function criterionTone(status: "SUPPORTED" | "PARTIAL" | "NOT_EVIDENCED") {
  if (status === "SUPPORTED") return "success" as const;
  if (status === "PARTIAL") return "warning" as const;
  return undefined;
}

export function RecruiterLensCard({ jobId }: { jobId: string }) {
  const lens = useQuery({
    queryKey: ["recruiter-lens", jobId],
    queryFn: ({ signal }) => recruiterLensApi.get(jobId, signal),
  });

  if (lens.isLoading) {
    return (
      <section className={styles.card} aria-label="Recruiter Lens">
        <p className={styles.loading}>Building your Recruiter Lens…</p>
      </section>
    );
  }

  if (lens.isError || !lens.data) {
    return (
      <section className={styles.card} aria-label="Recruiter Lens">
        <p className={styles.error}>
          {lens.error instanceof Error
            ? lens.error.message
            : "Recruiter Lens is unavailable for this role."}
        </p>
      </section>
    );
  }

  const item = lens.data;

  return (
    <section className={styles.card} aria-labelledby="recruiter-lens-title">
      <div className={styles.header}>
        <div className={styles.title}>
          <ScanSearch size={21} />
          <div>
            <h3 id="recruiter-lens-title">Recruiter Lens</h3>
            <p>
              A candidate-side screening mirror: what your verified evidence makes obvious,
              what still looks thin, and where an interviewer is likely to dig deeper.
            </p>
          </div>
        </div>
        <div className={styles.tier} aria-label={`Recruiter Lens tier ${item.tier}`}>
          <strong>{item.tier}</strong>
          <span>readiness tier</span>
        </div>
      </div>

      <div className={styles.metrics}>
        <div className={styles.metric}>
          <strong>{item.score}%</strong>
          <span>screening readiness</span>
        </div>
        <div className={styles.metric}>
          <strong>{item.counts.supported}</strong>
          <span>supported</span>
        </div>
        <div className={styles.metric}>
          <strong>{item.counts.partial}</strong>
          <span>partial</span>
        </div>
        <div className={styles.metric}>
          <strong>{item.counts.not_evidenced}</strong>
          <span>not evidenced</span>
        </div>
      </div>

      <div className={styles.block}>
        <div className={styles.blockHeader}>
          <h4>What the posting appears to screen for</h4>
          <Badge>{titleCase(item.confidence)} confidence</Badge>
        </div>
        <div className={styles.criteria}>
          {item.criteria.slice(0, 7).map((criterion) => (
            <div className={styles.criterion} key={criterion.id}>
              <strong>{criterion.label}</strong>
              <Badge tone={criterionTone(criterion.status)}>
                {titleCase(criterion.status)}
              </Badge>
              {criterion.evidence ? (
                <p>
                  Evidence: {criterion.evidence.snippet}
                </p>
              ) : (
                <p>No explicit verified evidence found in your saved profile.</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {item.concerns.length ? (
        <div className={styles.block}>
          <div className={styles.blockHeader}>
            <h4>Likely recruiter concerns</h4>
          </div>
          <div className={styles.concerns}>
            {item.concerns.slice(0, 4).map((concern) => (
              <div className={styles.concern} key={`${concern.criterion_id}-${concern.message}`}>
                <AlertTriangle size={16} />
                <p>{concern.message}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {item.interview_questions.length ? (
        <div className={styles.block}>
          <div className={styles.blockHeader}>
            <h4>Questions those gaps could create</h4>
          </div>
          <div className={styles.questions}>
            {item.interview_questions.slice(0, 4).map((question) => (
              <div className={styles.question} key={`${question.criterion_id}-${question.question}`}>
                <MessageCircleQuestion size={16} />
                <p>{question.question}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <p className={styles.disclaimer}>
        <ShieldCheck size={16} />
        <span>{item.disclaimer}</span>
      </p>
    </section>
  );
}
