"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, BrainCircuit, FileText, Network, Trash2 } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { CareerWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Input,
  NativeSelect,
  PageHeader,
  Textarea,
} from "@/components/ui";
import { api, type CareerFactCategory, type CareerFactWrite } from "@/lib/api/client";
import { titleCase } from "@/lib/utils";
import styles from "./career-workspace.module.css";

const categories: Array<{ value: CareerFactCategory; label: string }> = [
  { value: "ACHIEVEMENT", label: "Achievement" },
  { value: "PROJECT", label: "Project" },
  { value: "METRIC", label: "Metric / measurable result" },
  { value: "RESPONSIBILITY", label: "Responsibility" },
  { value: "CERTIFICATION", label: "Certification" },
  { value: "LEADERSHIP_STORY", label: "Leadership story" },
  { value: "INTERVIEW_FEEDBACK", label: "Interview feedback" },
  { value: "CAREER_GOAL", label: "Career goal" },
];

function artifactSummary(content: Record<string, unknown>) {
  if (typeof content.summary === "string") return content.summary;
  if (typeof content.strategy_summary === "string") return content.strategy_summary;
  if (typeof content.cover_letter === "string") return "Application material prepared for your review.";
  return "Career preparation created from your verified evidence.";
}

export function CareerWorkspace() {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<CareerFactCategory>("ACHIEVEMENT");
  const [title, setTitle] = useState("");
  const [factText, setFactText] = useState("");
  const [tags, setTags] = useState("");

  const facts = useQuery({ queryKey: ["career-memory"], queryFn: ({ signal }) => api.careerMemory.list(signal) });
  const summary = useQuery({ queryKey: ["career-memory-summary"], queryFn: ({ signal }) => api.careerMemory.summary(signal) });
  const artifacts = useQuery({ queryKey: ["career-v2-artifacts", "all"], queryFn: ({ signal }) => api.careerV2.artifacts(undefined, signal) });

  const createFact = useMutation({
    mutationFn: (payload: CareerFactWrite) => api.careerMemory.create(payload),
    onSuccess: () => {
      setTitle("");
      setFactText("");
      setTags("");
      queryClient.invalidateQueries({ queryKey: ["career-memory"] });
      queryClient.invalidateQueries({ queryKey: ["career-memory-summary"] });
      toast.success("Career evidence added");
    },
    onError: () => toast.error("We couldn't save that career evidence."),
  });

  const removeFact = useMutation({
    mutationFn: (factId: string) => api.careerMemory.remove(factId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["career-memory"] });
      queryClient.invalidateQueries({ queryKey: ["career-memory-summary"] });
      toast.success("Career evidence archived");
    },
    onError: () => toast.error("We couldn't archive that career evidence."),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanedFact = factText.trim();
    if (!cleanedFact) return;
    createFact.mutate({
      category,
      title: title.trim() || null,
      fact_text: cleanedFact,
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
    });
  }

  if (facts.isError) return <ErrorState message={facts.error.message} retry={() => facts.refetch()} />;

  return (
    <div>
      <CareerWorkspaceTabs activeHref="/career" />
      <PageHeader
        eyebrow="Career Coach"
        title="Turn your experience into your next move."
        description="Keep the evidence that makes you credible in one place, then use it across resumes, applications, networking, and interview preparation."
      />

      <div className="cx-coach-actions">
        <Link href="/resume/studio" className="cx-coach-action"><span><FileText size={19} /></span><div><strong>Strengthen your resume</strong><small>Create and review job-specific versions</small></div></Link>
        <Link href="/network" className="cx-coach-action"><span><Network size={19} /></span><div><strong>Build your network</strong><small>Keep recruiters, referrals, and follow-ups together</small></div></Link>
        <Link href="/analytics" className="cx-coach-action"><span><BarChart3 size={19} /></span><div><strong>See your progress</strong><small>Understand where your search is moving</small></div></Link>
      </div>

      <div className={styles.layout}>
        <div className={styles.stack}>
          <Card className={styles.card}>
            <div className="section-header">
              <div>
                <p className="eyebrow">What ApplyAI knows about you</p>
                <h2>Add career evidence</h2>
                <p>Save achievements and stories you would be comfortable defending in a resume or interview.</p>
              </div>
            </div>
            <form className={styles.form} onSubmit={submit}>
              <div className={styles.formGrid}>
                <label className="form-field">
                  <span>Evidence type</span>
                  <NativeSelect value={category} onChange={(event) => setCategory(event.target.value as CareerFactCategory)}>
                    {categories.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </NativeSelect>
                </label>
                <label className="form-field">
                  <span>Short title</span>
                  <Input value={title} maxLength={255} placeholder="e.g. Platform migration" onChange={(event) => setTitle(event.target.value)} />
                </label>
              </div>
              <label className="form-field">
                <span>What happened?</span>
                <Textarea value={factText} maxLength={8000} placeholder="What did you do, what was your contribution, and what result can you support?" onChange={(event) => setFactText(event.target.value)} required />
              </label>
              <label className="form-field">
                <span>Helpful tags</span>
                <Input value={tags} placeholder="leadership, snowflake, migration" onChange={(event) => setTags(event.target.value)} />
              </label>
              <div className={styles.formActions}>
                <p>ApplyAI uses saved evidence to personalize your career materials without silently turning AI guesses into facts.</p>
                <Button type="submit" disabled={createFact.isPending || !factText.trim()}>Save evidence</Button>
              </div>
            </form>
          </Card>

          <Card className={styles.card}>
            <div className="section-header">
              <div>
                <h2>Your evidence library</h2>
                <p>{summary.data?.verified_fact_count ?? facts.data?.length ?? 0} facts ready to support matching and preparation.</p>
              </div>
            </div>
            {facts.data?.length ? (
              <div className={styles.factList}>
                {facts.data.map((fact) => (
                  <article className={styles.fact} key={fact.id}>
                    <div className={styles.factHeader}>
                      <div><Badge tone="success">{titleCase(fact.category)}</Badge>{fact.title ? <h3>{fact.title}</h3> : null}</div>
                      <button className={styles.iconButton} type="button" aria-label="Archive career evidence" disabled={removeFact.isPending} onClick={() => removeFact.mutate(fact.id)}><Trash2 size={17} /></button>
                    </div>
                    <p>{fact.fact_text}</p>
                    {fact.tags.length ? <div className={styles.tags}>{fact.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}</div> : null}
                  </article>
                ))}
              </div>
            ) : <p className={styles.empty}>Add a few strong achievements, projects, or goals. Your verified profile and resume remain available too.</p>}
          </Card>
        </div>

        <aside className={styles.stack}>
          <Card className={styles.card}>
            <div className={styles.summaryRow}>
              <div><p className="eyebrow">Your foundation</p><h2>Career profile</h2></div>
              <BrainCircuit size={24} aria-hidden="true" />
            </div>
            <div className={styles.summaryGrid}>
              <div className={styles.summaryTile}><strong>{summary.data?.verified_fact_count ?? 0}</strong><span>verified facts</span></div>
              <div className={styles.summaryTile}><strong>{Object.keys(summary.data?.by_category ?? {}).length}</strong><span>evidence types</span></div>
              {Object.entries(summary.data?.by_category ?? {}).slice(0, 4).map(([name, count]) => <div className={styles.summaryTile} key={name}><strong>{count}</strong><span>{titleCase(name)}</span></div>)}
            </div>
          </Card>

          <Card className={styles.card}>
            <div className="section-header"><div><h2>Recent preparation</h2><p>Work ApplyAI has prepared from your career evidence.</p></div></div>
            {artifacts.data?.items.length ? (
              <div className={styles.artifactList}>
                {artifacts.data.items.slice(0, 6).map((artifact) => (
                  <article className={styles.artifact} key={artifact.id}>
                    <div className={styles.artifactHeader}><h3>{titleCase(artifact.artifact_type)}</h3><Badge tone={artifact.candidate_verified ? "success" : "warning"}>{artifact.candidate_verified ? "Reviewed" : "Needs review"}</Badge></div>
                    <p>{artifactSummary(artifact.content)}</p>
                  </article>
                ))}
              </div>
            ) : <p className={styles.empty}>Your resume, application, and interview preparation will appear here as you use ApplyAI.</p>}
          </Card>
        </aside>
      </div>
    </div>
  );
}
