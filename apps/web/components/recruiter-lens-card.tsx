"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
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
  const [showAllCriteria, setShowAllCriteria] = useState(false);
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
      setShowAllCriteria(false);
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
      <section className={styles.card} aria-label="Recruiter Lens" aria-busy="true">
        <div className={styles.loading}><Sparkles size={18} /> Building your evidence-based Recruiter Lens…</div>
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
  const preparationSummary = item.counts.not_evidenced > 0
    ? `${item.counts.supported} supported, ${item.counts.partial} partial, and ${item.counts.not_evidenced} not yet evidenced. Start with the gaps that matter most to this perspective.`
    : item.counts.partial > 0
      ? `${item.counts.supported} supported and ${item.counts.partial} partially evidenced. Strengthen the partial areas before you rely on them.`
      : `Your saved evidence supports all ${item.counts.supported} criteria surfaced by this perspective.`;

  const changePerspective = (nextMode: RecruiterLensMode) => {
    setCriteriaSetId("");
    setMode(nextMode);
    setShowAllCriteria(false);
  };

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
          <div className={styles.scoreVisual} aria-label={`Readiness score ${item.score}`}>
            <strong>{item.score}</strong>
            <span>readiness</span>
          </div>
          <div className={styles.tier} aria-label={`Recruiter Lens tier ${item.tier}`}>
            <strong>{item.tier}</strong>
            <span>tier</span>
          </div>
        </div>
      </div>

      <div className={styles.summaryStrip} aria-label="Recruiter Lens summary">
        <CheckCircle2 size={18} aria-hidden="true" />
        <div>
          <strong>What matters first</strong>
          <p>{preparationSummary}</p>
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
              onClick={() => changePerspective(perspective.value)}
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
              onChange={(event) => changePerspective(event.target.value as RecruiterLensMode)}
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
                setShowAllCriteria(false);
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
        <div className={styles.metric} data-evidence-state="supported">
          <CheckCircle2 size={16} />
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
        <div className={styles.metric}>
          <strong>{titleCase(item.confidence)}</strong>
          <span>analysis confidence</span>
        </div>
      </div>

      <div className={styles.block}>
        <div className={styles.blockHeader}>
          <div><h4>Evidence that shapes this perspective</h4><p>Start with the first three criteria; expand only when you need the full screening detail.</p></div>
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
                <p><span>Evidence</span>{criterion.evidence.snippet}</p>
              ) : (
                <p><span>Evidence</span>No explicit verified evidence found in your saved profile.</p>
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
            <ChevronDown size={16} className={showAllCriteria ? styles.chevronOpen : undefined} />
            {showAllCriteria ? "Show less screening detail" : `Show ${hiddenCriteriaCount} more criteria`}
          </Button>
        ) : null}
      </div>

      <div className={styles.insightGrid}>
        <details className={`${styles.block} ${styles.insightDisclosure}`}>
          <summary className={styles.insightSummary}>
            <span><AlertTriangle size={16} />Potential concerns</span>
            <Badge tone={item.concerns.length ? "warning" : "success"}>{item.concerns.length}</Badge>
          </summary>
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
        </details>

        <details className={`${styles.block} ${styles.insightDisclosure}`}>
          <summary className={styles.insightSummary}>
            <span><MessageCircleQuestion size={16} />Questions to prepare for</span>
            <Badge tone="info">{item.interview_questions.length}</Badge>
          </summary>
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
        </details>
      </div>

      <p className={styles.disclaimer}>
        <ShieldCheck size={16} />
        <span>{item.disclaimer} Recruiter Lens is preparation guidance—not an employer decision, viewer identity signal, or hiring probability.</span>
      </p>
    </section>
  );
}
