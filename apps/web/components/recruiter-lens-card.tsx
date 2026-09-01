"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  MessageCircleQuestion,
  Printer,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Input, NativeSelect } from "@/components/ui";
import { growthApi } from "@/lib/api/growth";
import { recruiterLensApi, type RecruiterLensMode } from "@/lib/api/recruiter-lens";
import { titleCase } from "@/lib/utils";
import styles from "./recruiter-lens-card.module.css";

function criterionTone(status: "SUPPORTED" | "PARTIAL" | "NOT_EVIDENCED") {
  if (status === "SUPPORTED") return "success" as const;
  if (status === "PARTIAL") return "warning" as const;
  return undefined;
}

export function RecruiterLensCard({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<RecruiterLensMode>("DEFAULT_RECRUITER");
  const [criteriaSetId, setCriteriaSetId] = useState("");
  const [setName, setSetName] = useState("");
  const [criterionLabel, setCriterionLabel] = useState("");
  const criteriaSets = useQuery({
    queryKey: ["recruiter-lens-criteria-sets"],
    queryFn: ({ signal }) => growthApi.criteriaSets.list(signal),
  });
  const lens = useQuery({
    queryKey: ["recruiter-lens", jobId, mode, criteriaSetId],
    queryFn: ({ signal }) => recruiterLensApi.get(
      jobId,
      { mode, criteriaSetId: criteriaSetId || null },
      signal,
    ),
  });
  const createSet = useMutation({
    mutationFn: () => growthApi.criteriaSets.create({
      name: setName,
      mode: "CUSTOM",
      criteria: [{ label: criterionLabel, required: true, weight: 2 }],
    }),
    onSuccess: async (created) => {
      setSetName("");
      setCriterionLabel("");
      setCriteriaSetId(created.id);
      setMode("CUSTOM");
      await queryClient.invalidateQueries({ queryKey: ["recruiter-lens-criteria-sets"] });
      toast.success("Self-assessment criteria saved");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not save criteria"),
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

      <div className={styles.block}>
        <div className={styles.blockHeader}>
          <h4>Screening perspective</h4>
          <Button variant="ghost" size="small" onClick={() => window.print()}>
            <Printer size={15} />Print report
          </Button>
        </div>
        <div className="form-grid">
          <label className="form-field">
            <span>Perspective</span>
            <NativeSelect
              value={mode}
              onChange={(event) => {
                setCriteriaSetId("");
                setMode(event.target.value as RecruiterLensMode);
              }}
            >
              <option value="DEFAULT_RECRUITER">Default recruiter</option>
              <option value="STRICT_MUST_HAVE">Strict must-have</option>
              <option value="HIRING_MANAGER">Hiring manager</option>
              <option value="TECHNICAL">Technical</option>
              <option value="CUSTOM">Custom</option>
            </NativeSelect>
          </label>
          <label className="form-field">
            <span>Saved self-assessment criteria</span>
            <NativeSelect
              value={criteriaSetId}
              onChange={(event) => {
                setCriteriaSetId(event.target.value);
                if (event.target.value) setMode("CUSTOM");
              }}
            >
              <option value="">Use posting criteria</option>
              {(criteriaSets.data ?? []).map((criteriaSet) => (
                <option value={criteriaSet.id} key={criteriaSet.id}>{criteriaSet.name}</option>
              ))}
            </NativeSelect>
          </label>
        </div>
        <details>
          <summary>Create a reusable candidate-only criterion</summary>
          <div className="form-grid" style={{ marginTop: 12 }}>
            <label className="form-field">
              <span>Set name</span>
              <Input value={setName} maxLength={120} onChange={(event) => setSetName(event.target.value)} placeholder="Strict technical" />
            </label>
            <label className="form-field">
              <span>Criterion</span>
              <Input value={criterionLabel} maxLength={300} onChange={(event) => setCriterionLabel(event.target.value)} placeholder="Production Python experience" />
            </label>
            <Button
              type="button"
              disabled={!setName.trim() || !criterionLabel.trim() || createSet.isPending}
              onClick={() => createSet.mutate()}
            >
              Save criteria set
            </Button>
          </div>
          <p className={styles.disclaimer}>
            Protected-characteristic criteria are blocked. These sets are for your own preparation and never rank other candidates.
          </p>
        </details>
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
          <h4>What this perspective screens for</h4>
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
                <p>Evidence: {criterion.evidence.snippet}</p>
              ) : (
                <p>No explicit verified evidence found in your saved profile.</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {item.concerns.length ? (
        <div className={styles.block}>
          <div className={styles.blockHeader}><h4>Likely recruiter concerns</h4></div>
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
          <div className={styles.blockHeader}><h4>Questions those gaps could create</h4></div>
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
