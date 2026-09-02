"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Link2,
  MessageCircleQuestion,
  Printer,
  ScanSearch,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Input, NativeSelect } from "@/components/ui";
import { growthApi } from "@/lib/api/growth";
import { recruiterLensApi, type RecruiterLensMode } from "@/lib/api/recruiter-lens";
import { titleCase } from "@/lib/utils";
import styles from "./recruiter-lens-card.module.css";

const perspectives: Array<{ value: RecruiterLensMode; label: string }> = [
  { value: "DEFAULT_RECRUITER", label: "Default Recruiter" },
  { value: "STRICT_MUST_HAVE", label: "Strict Must-Have" },
  { value: "HIRING_MANAGER", label: "Hiring Manager" },
  { value: "TECHNICAL", label: "Technical" },
  { value: "CUSTOM", label: "Custom" },
];

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
  const createReportShare = useMutation({
    mutationFn: () => recruiterLensApi.createReportShare(jobId, {
      mode,
      criteriaSetId: criteriaSetId || null,
    }),
    onSuccess: async (share) => {
      const absoluteUrl = `${window.location.origin}${share.public_path}`;
      try {
        await navigator.clipboard.writeText(absoluteUrl);
        toast.success("Private Recruiter Lens report link copied");
      } catch {
        toast.success(`Report link ready: ${absoluteUrl}`);
      }
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not create report link"),
  });

  if (lens.isLoading) {
    return (
      <section className={styles.card} aria-label="Recruiter Lens">
        <div className={styles.loading}><Sparkles size={18} /> Building your evidence-based Recruiter Lens…</div>
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
          <span className={styles.titleIcon}><ScanSearch size={22} /></span>
          <div>
            <span className={styles.kicker}>Candidate preparation mirror</span>
            <h3 id="recruiter-lens-title">Recruiter Lens</h3>
            <p>
              If someone screened your résumé against this role, what would your verified evidence make obvious—and where would they ask for more?
            </p>
          </div>
        </div>
        <div className={styles.scoreCluster}>
          <div className={styles.scoreVisual}>
            <strong>{item.score}</strong>
            <span>readiness</span>
          </div>
          <div className={styles.tier} aria-label={`Recruiter Lens tier ${item.tier}`}>
            <strong>{item.tier}</strong>
            <span>tier</span>
          </div>
        </div>
      </div>

      <div className={styles.perspectivePanel}>
        <div className={styles.blockHeader}>
          <div>
            <h4>Screening perspective</h4>
            <p>Change the lens without changing your underlying career evidence.</p>
          </div>
          <div className={styles.reportActions}>
            <Button variant="ghost" size="small" onClick={() => window.print()}>
              <Printer size={15} />Print report
            </Button>
            <Button
              variant="ghost"
              size="small"
              disabled={createReportShare.isPending}
              onClick={() => createReportShare.mutate()}
            >
              <Link2 size={15} />Share private report
            </Button>
          </div>
        </div>

        <div className={styles.perspectiveButtons} aria-label="Recruiter Lens perspectives">
          {perspectives.map((perspective) => (
            <button
              key={perspective.value}
              type="button"
              className={mode === perspective.value && !criteriaSetId ? styles.perspectiveActive : styles.perspectiveButton}
              onClick={() => {
                setCriteriaSetId("");
                setMode(perspective.value);
              }}
              aria-pressed={mode === perspective.value && !criteriaSetId}
            >
              {perspective.label}
            </button>
          ))}
        </div>

        <div className={styles.selectFallback}>
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
        </div>

        <div className={styles.savedCriteriaRow}>
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
          <details className={styles.customCriteria}>
            <summary>Create reusable criteria</summary>
            <div className={styles.customCriteriaForm}>
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
              <p className={styles.microcopy}>
                Protected-characteristic criteria are blocked. These sets only help you prepare your own application.
              </p>
            </div>
          </details>
        </div>
      </div>

      <div className={styles.metrics}>
        <div className={styles.metric}>
          <CheckCircle2 size={16} />
          <strong>{item.counts.supported}</strong>
          <span>supported</span>
        </div>
        <div className={styles.metric}>
          <strong>{item.counts.partial}</strong>
          <span>partial evidence</span>
        </div>
        <div className={styles.metric}>
          <strong>{item.counts.not_evidenced}</strong>
          <span>not evidenced</span>
        </div>
        <div className={styles.metric}>
          <strong>{titleCase(item.confidence)}</strong>
          <span>analysis confidence</span>
        </div>
      </div>

      <div className={styles.block}>
        <div className={styles.blockHeader}>
          <div><h4>What this perspective screens for</h4><p>Every status is tied to evidence in your saved candidate profile.</p></div>
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
                <p><span>Evidence</span>{criterion.evidence.snippet}</p>
              ) : (
                <p><span>Evidence</span>No explicit verified evidence found in your saved profile.</p>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className={styles.insightGrid}>
        <div className={styles.block}>
          <div className={styles.blockHeader}><h4>Potential concerns</h4></div>
          {item.concerns.length ? (
            <div className={styles.concerns}>
              {item.concerns.slice(0, 4).map((concern) => (
                <div className={styles.concern} key={`${concern.criterion_id}-${concern.message}`}>
                  <AlertTriangle size={16} />
                  <p>{concern.message}</p>
                </div>
              ))}
            </div>
          ) : <p className={styles.clearState}>No additional evidence concerns surfaced in this perspective.</p>}
        </div>

        <div className={styles.block}>
          <div className={styles.blockHeader}><h4>Questions to prepare for</h4></div>
          {item.interview_questions.length ? (
            <div className={styles.questions}>
              {item.interview_questions.slice(0, 4).map((question) => (
                <div className={styles.question} key={`${question.criterion_id}-${question.question}`}>
                  <MessageCircleQuestion size={16} />
                  <p>{question.question}</p>
                </div>
              ))}
            </div>
          ) : <p className={styles.clearState}>No gap-driven questions are needed from this evidence set.</p>}
        </div>
      </div>

      <p className={styles.disclaimer}>
        <ShieldCheck size={16} />
        <span>{item.disclaimer} Recruiter Lens is preparation guidance—not an employer decision, viewer identity signal, or hiring probability.</span>
      </p>
    </section>
  );
}
