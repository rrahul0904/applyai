"use client";

import { ArrowRight, CheckCircle2, Code2, GitBranch, Github, ShieldCheck, Sparkles, Target, XCircle } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import type { ProofOfWorkReport, TargetRole } from "@/lib/proof-of-work";
import styles from "./proof-of-work-view.module.css";

const roles: Array<{ value: TargetRole; label: string }> = [
  { value: "fullstack", label: "Full-stack engineer" },
  { value: "frontend", label: "Frontend engineer" },
  { value: "backend", label: "Backend engineer" },
  { value: "data", label: "Data engineer" },
  { value: "mobile", label: "Mobile engineer" },
];

function depthClass(depth: string) {
  if (depth === "Sustained") return styles.sustained;
  if (depth === "Repeated") return styles.repeated;
  return styles.observed;
}

export function ProofOfWorkView() {
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<TargetRole>("fullstack");
  const [report, setReport] = useState<ProofOfWorkReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const response = await fetch(`/api/proof-of-work/github?username=${encodeURIComponent(username.trim())}&role=${role}`);
      const payload = await response.json() as ProofOfWorkReport | { error?: string };
      if (!response.ok) {
        throw new Error("error" in payload && payload.error ? payload.error : "Unable to analyze this GitHub account.");
      }
      setReport(payload as ProofOfWorkReport);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to analyze this GitHub account.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.nav}>
        <Link href="/" className={styles.brand}><span>A</span>ApplyAI</Link>
        <div className={styles.navActions}>
          <span><ShieldCheck size={15} /> Public metadata only</span>
          <Link href="/portfolio">Back to portfolio</Link>
        </div>
      </header>

      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}><Sparkles size={15} /> Proof of Work Lab · RE-370 prototype</p>
          <h1>Turn what you built into career evidence.</h1>
          <p>
            Analyze a bounded set of recent public GitHub repositories, see the evidence signals they expose,
            compare those signals with a target role, and get one concrete next project to close a visible gap.
          </p>
          <div className={styles.guardrails}>
            <span><ShieldCheck size={16} /> No source-code bodies read</span>
            <span><GitBranch size={16} /> Max 6 owned repositories</span>
            <span><Target size={16} /> No hiring or proficiency score</span>
          </div>
        </div>

        <form className={styles.formCard} onSubmit={analyze}>
          <div>
            <label htmlFor="github-username">Public GitHub username</label>
            <div className={styles.inputShell}><Github size={18} /><input id="github-username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="octocat" required autoComplete="off" /></div>
          </div>
          <div>
            <label htmlFor="target-role">Target role</label>
            <select id="target-role" value={role} onChange={(event) => setRole(event.target.value as TargetRole)}>
              {roles.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </div>
          <button type="submit" disabled={loading || !username.trim()}>
            {loading ? "Analyzing evidence…" : <>Analyze proof of work <ArrowRight size={17} /></>}
          </button>
          <p className={styles.formNote}>This prototype uses public GitHub REST metadata and root artifact names only. Nothing is written back to GitHub.</p>
          {error ? <p className={styles.error} role="alert">{error}</p> : null}
        </form>
      </section>

      {!report ? (
        <section className={styles.explainer} aria-label="How the prototype works">
          <article><span>01</span><h2>Observe</h2><p>Look for deterministic signals such as primary language, tsconfig, Dockerfile, tests, migrations, Terraform and CI directories.</p></article>
          <article><span>02</span><h2>Attribute</h2><p>Every signal points back to the repository where it was observed. Repetition becomes evidence depth, not a competency grade.</p></article>
          <article><span>03</span><h2>Close a gap</h2><p>Compare those signals with a transparent target-role checklist and turn the first unmet area into a bounded build brief.</p></article>
        </section>
      ) : (
        <section className={styles.results} aria-live="polite">
          <div className={styles.resultHeader}>
            <div><p className={styles.eyebrow}>Evidence report</p><h2>@{report.username} → {roles.find((item) => item.value === report.targetRole)?.label}</h2><p>{report.methodology.note}</p></div>
            <div className={styles.scanMetric}><strong>{report.methodology.scannedRepositoryCount}</strong><span>repos scanned</span></div>
          </div>

          <div className={styles.gridTwo}>
            <article className={styles.panel}>
              <div className={styles.panelTitle}><Code2 size={19} /><div><h3>Observed skill signals</h3><p>Depth means recurrence across scanned repos.</p></div></div>
              {report.skillEvidence.length ? <div className={styles.skillList}>
                {report.skillEvidence.map((item) => (
                  <div className={styles.skillRow} key={item.skill}>
                    <div><strong>{item.skill}</strong><span>{item.repositories.join(" · ")}</span></div>
                    <span className={`${styles.depth} ${depthClass(item.depth)}`}>{item.depth} · {item.repositoryCount}</span>
                  </div>
                ))}
              </div> : <p className={styles.empty}>No supported root-level evidence signals were observed in the bounded scan.</p>}
            </article>

            <article className={styles.panel}>
              <div className={styles.panelTitle}><Target size={19} /><div><h3>Target-role evidence map</h3><p>Transparent requirements; no opaque match percentage.</p></div></div>
              <div className={styles.requirementList}>
                {report.requirements.map((item) => (
                  <div className={styles.requirement} key={item.label}>
                    {item.met ? <CheckCircle2 size={18} className={styles.metIcon} /> : <XCircle size={18} className={styles.gapIcon} />}
                    <div><strong>{item.label}</strong><span>{item.met ? `Observed via ${item.evidence.join(", ")}` : `Look for ${item.acceptedSignals.join(" or ")}`}</span></div>
                  </div>
                ))}
              </div>
            </article>
          </div>

          <article className={styles.nextBuild}>
            <div><p className={styles.eyebrow}>Next proof-building project</p><h3>{report.nextBuild.title}</h3><p>{report.nextBuild.rationale}</p></div>
            <ul>{report.nextBuild.acceptanceCriteria.map((criterion) => <li key={criterion}><CheckCircle2 size={16} />{criterion}</li>)}</ul>
          </article>

          <article className={styles.panel}>
            <div className={styles.panelTitle}><Github size={19} /><div><h3>Repository evidence receipts</h3><p>Exactly what the bounded scan used.</p></div></div>
            <div className={styles.repoGrid}>
              {report.repositories.map((repository) => (
                <a href={repository.url} target="_blank" rel="noreferrer" key={repository.url} className={styles.repoCard}>
                  <strong>{repository.name}</strong>
                  <span>{repository.language || "Language not reported"}</span>
                  <p>{repository.signals.length ? repository.signals.join(" · ") : "No supported root-level signals observed"}</p>
                </a>
              ))}
            </div>
          </article>
        </section>
      )}

      <footer className={styles.footer}>
        <p><strong>Clean-room prototype.</strong> Inspired by publicly observable Workmark product behavior; independently implemented for ApplyAI without copying private source code or claiming product parity.</p>
      </footer>
    </main>
  );
}
