"use client";

import {
  ArrowRight,
  Check,
  CheckCircle2,
  FileCheck2,
  FileText,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api, type ProfileWrite } from "@/lib/api/client";
import styles from "./beta.module.css";

type Phase = "loading" | "ready" | "auth" | "error";
type Stage = "matches" | "tailoring" | "assistant" | "complete";
type Decision = "PENDING" | "APPROVED" | "REJECTED";

type MatchFactor = {
  factor: string;
  score: number;
  maximum: number;
  reason: string;
};

type Match = {
  job_id: string;
  title: string;
  company_name: string;
  location: string | null;
  work_mode: string | null;
  minimum_compensation: number | null;
  maximum_compensation: number | null;
  posted_at: string | null;
  last_seen_at: string;
  description: string;
  match_score: number;
  fit_band: string;
  decision: string;
  confidence: string;
  engine_version: string;
  breakdown: MatchFactor[];
  strengths: string[];
  risks: string[];
  matched_skills: string[];
  missing_skills: string[];
  missing_requirements: string[];
  source_url: string | null;
  summary: string;
};

type MatchResponse = {
  engine_version: string;
  disclaimer: string;
  items: Match[];
};

type TailoringEdit = {
  index: number;
  current: string;
  suggested: string;
  evidence: string;
  text: string;
  decision: Decision;
};

type Tailoring = {
  job_id: string;
  application_id: string | null;
  job_title: string;
  company_name: string;
  edits: TailoringEdit[];
  safety: { policy: string; message: string };
};

type AssistantQuestion = {
  question: string;
  draft: string;
  answer: string;
  evidence: string[];
  user_verified: boolean;
};

type ChecklistItem = {
  id: string;
  label: string;
  complete: boolean;
  weight: number;
};

type Assistant = {
  application_id: string | null;
  job_id: string;
  job_title: string;
  company_name: string;
  match: Match;
  cover_letter: string;
  cover_letter_verified: boolean;
  questions: AssistantQuestion[];
  checklist: ChecklistItem[];
  readiness_score: number;
  ready_to_finalize: boolean;
  source_url: string | null;
  external_submission_required: boolean;
  notice: string;
};

type FinalPackage = {
  application_id: string;
  job_id: string;
  current_status: string;
  readiness_score: number;
  package_manifest: string;
  source_url: string | null;
  external_submission_required: boolean;
};

const BETA_PROFILE: ProfileWrite = {
  headline: "Senior data engineering leader",
  current_title: "Senior Data Engineering Manager",
  summary:
    "Data platform leader with 12 years of experience building reliable analytics and machine-learning infrastructure for regulated and high-growth organizations.",
  years_experience: 12,
  target_roles: [
    "Data Engineering Manager",
    "Analytics Engineering Manager",
    "Machine Learning Engineering Manager",
  ],
  location_text: "Boston, MA",
  work_modes: ["REMOTE", "HYBRID"],
  minimum_compensation: 90000,
  experiences: [
    {
      company_name: "Atlas Health",
      title: "Senior Data Engineering Manager",
      start_date: "2021-01-01",
      end_date: null,
      description:
        "Built and led a 12-person data engineering organization and reduced pipeline delivery time by 35% while improving reliability across four business units.",
      provenance: "USER_VERIFIED",
    },
    {
      company_name: "Summit Commerce",
      title: "Data Platform Lead",
      start_date: "2017-01-01",
      end_date: "2020-12-31",
      description:
        "Modernized AWS and Snowflake data platforms, introduced shared analytics engineering standards, and partnered with product leaders on a three-year roadmap.",
      provenance: "USER_VERIFIED",
    },
  ],
  education: [],
  skills: [
    { name: "Python", provenance: "USER_VERIFIED" },
    { name: "SQL", provenance: "USER_VERIFIED" },
    { name: "Analytics", provenance: "USER_VERIFIED" },
    { name: "Machine learning", provenance: "USER_VERIFIED" },
    { name: "AWS", provenance: "USER_VERIFIED" },
    { name: "Snowflake", provenance: "USER_VERIFIED" },
  ],
};

async function careerRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend/career-v1${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: { message?: string; incomplete?: string[] } }
      | null;
    const incomplete = payload?.error?.incomplete;
    throw new Error(
      incomplete?.length
        ? `${payload?.error?.message ?? "Review required"} ${incomplete.join("; ")}`
        : payload?.error?.message ?? "The career assistant request failed.",
    );
  }
  return response.json() as Promise<T>;
}

function money(value: number | null) {
  if (value == null) return null;
  return value >= 1000 ? `$${Math.round(value / 1000)}K` : `$${value.toLocaleString()}`;
}

function salary(match: Match) {
  const minimum = money(match.minimum_compensation);
  const maximum = money(match.maximum_compensation);
  if (minimum && maximum) return `${minimum}–${maximum}`;
  if (minimum) return `${minimum}+`;
  if (maximum) return `Up to ${maximum}`;
  return "Salary not listed";
}

export function CandidateBetaJourney() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [stage, setStage] = useState<Stage>("matches");
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [tailoring, setTailoring] = useState<Tailoring | null>(null);
  const [assistant, setAssistant] = useState<Assistant | null>(null);
  const [finalPackage, setFinalPackage] = useState<FinalPackage | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedMatch = useMemo(
    () => matches.find((item) => item.job_id === selectedJobId) ?? matches[0] ?? null,
    [matches, selectedJobId],
  );

  const initialize = useCallback(async () => {
    setPhase("loading");
    setError(null);
    try {
      try {
        await api.auth.me();
      } catch (cause) {
        if (!(cause instanceof ApiError) || cause.status !== 401) throw cause;
        const sessionResponse = await fetch("/api/demo-session", { method: "POST" });
        if (!sessionResponse.ok) {
          setPhase("auth");
          return;
        }
        await api.auth.me();
      }
      const profile = await api.profile.get();
      if (!profile) await api.profile.save(BETA_PROFILE);
      const response = await careerRequest<MatchResponse>("/matches?limit=12");
      setMatches(response.items);
      setSelectedJobId((current) => current ?? response.items[0]?.job_id ?? null);
      setPhase("ready");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The beta workspace could not load.");
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  const openTailoring = async () => {
    if (!selectedMatch) return;
    setBusy("tailoring");
    setError(null);
    try {
      const response = await careerRequest<Tailoring>(
        `/tailoring/${selectedMatch.job_id}`,
      );
      setTailoring(response);
      setStage("tailoring");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Tailoring could not load.");
    } finally {
      setBusy(null);
    }
  };

  const updateTailoring = (
    index: number,
    change: Partial<Pick<TailoringEdit, "text" | "decision">>,
  ) => {
    setTailoring((current) =>
      current
        ? {
            ...current,
            edits: current.edits.map((item) =>
              item.index === index ? { ...item, ...change } : item,
            ),
          }
        : current,
    );
  };

  const saveAndFinalizeResume = async () => {
    if (!tailoring) return;
    setBusy("finalize-resume");
    setError(null);
    try {
      const saved = await careerRequest<Tailoring>(
        `/tailoring/${tailoring.job_id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            edits: tailoring.edits.map((item) => ({
              index: item.index,
              text: item.text,
              decision: item.decision,
            })),
          }),
        },
      );
      setTailoring(saved);
      await careerRequest(`/tailoring/${tailoring.job_id}/finalize`, {
        method: "POST",
      });
      const assistantResponse = await careerRequest<Assistant>(
        `/application-assistant/${tailoring.job_id}`,
      );
      setAssistant(assistantResponse);
      setStage("assistant");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "The tailored resume could not be finalized.",
      );
    } finally {
      setBusy(null);
    }
  };

  const updateQuestion = (
    index: number,
    change: Partial<Pick<AssistantQuestion, "answer" | "user_verified">>,
  ) => {
    setAssistant((current) =>
      current
        ? {
            ...current,
            questions: current.questions.map((item, itemIndex) =>
              itemIndex === index ? { ...item, ...change } : item,
            ),
          }
        : current,
    );
  };

  const saveApplicationReview = async () => {
    if (!assistant) return null;
    const response = await careerRequest<Assistant>(
      `/application-assistant/${assistant.job_id}`,
      {
        method: "PUT",
        body: JSON.stringify({
          cover_letter: assistant.cover_letter,
          cover_letter_verified: assistant.cover_letter_verified,
          answers: assistant.questions.map((item) => ({
            question: item.question,
            answer: item.answer,
            user_verified: item.user_verified,
          })),
        }),
      },
    );
    setAssistant(response);
    return response;
  };

  const finalizeApplication = async () => {
    if (!assistant) return;
    setBusy("finalize-application");
    setError(null);
    try {
      const saved = await saveApplicationReview();
      if (!saved?.ready_to_finalize) {
        throw new Error("Review and verify the cover letter and every application answer.");
      }
      const result = await careerRequest<FinalPackage>(
        `/application-assistant/${assistant.job_id}/finalize`,
        { method: "POST" },
      );
      setFinalPackage(result);
      setStage("complete");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "The application package could not be finalized.",
      );
    } finally {
      setBusy(null);
    }
  };

  if (phase === "loading") {
    return (
      <main className={styles.centered}>
        <LoaderCircle className={styles.spinner} />
        <h1>Preparing your candidate workspace</h1>
        <p>Loading your verified profile, current roles, and application history.</p>
      </main>
    );
  }

  if (phase === "auth") {
    return (
      <main className={styles.centered}>
        <ShieldCheck size={44} />
        <h1>Sign in to continue</h1>
        <p>The account-free identity is available only in controlled local and test environments.</p>
        <a className={styles.primaryButton} href="/sign-in">
          Sign in
        </a>
      </main>
    );
  }

  if (phase === "error") {
    return (
      <main className={styles.centered}>
        <h1>The beta workspace could not load</h1>
        <p>{error}</p>
        <button className={styles.primaryButton} onClick={() => void initialize()}>
          Try again
        </button>
      </main>
    );
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <a className={styles.brand} href="/">
          <span>A</span>
          ApplyAI
        </a>
        <div className={styles.betaBadge}>
          <Sparkles size={15} />
          Candidate beta
        </div>
      </header>

      <section className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>From job discovery to a reviewed application package</p>
          <h1>Apply to the right role with evidence you can defend.</h1>
          <p>
            ApplyAI ranks opportunities, explains the tradeoffs, tailors verified experience,
            and prepares application materials for your approval.
          </p>
        </div>
        <div className={styles.stepper}>
          {[
            ["matches", "1", "Choose"],
            ["tailoring", "2", "Tailor"],
            ["assistant", "3", "Review"],
            ["complete", "4", "Ready"],
          ].map(([id, number, label]) => (
            <div
              className={`${styles.step} ${stage === id ? styles.activeStep : ""}`}
              key={id}
            >
              <span>{number}</span>
              <small>{label}</small>
            </div>
          ))}
        </div>
      </section>

      {error ? <div className={styles.errorBanner}>{error}</div> : null}

      {stage === "matches" && selectedMatch ? (
        <section className={styles.workspace}>
          <aside className={styles.matchList}>
            <div className={styles.sectionTitle}>
              <Target size={19} />
              <div>
                <p className={styles.eyebrow}>Prioritized roles</p>
                <h2>Where your time is best spent</h2>
              </div>
            </div>
            {matches.map((match) => (
              <button
                className={`${styles.matchCard} ${
                  selectedMatch.job_id === match.job_id ? styles.selectedCard : ""
                }`}
                key={match.job_id}
                onClick={() => setSelectedJobId(match.job_id)}
              >
                <div>
                  <strong>{match.title}</strong>
                  <span>{match.company_name}</span>
                </div>
                <b>{match.match_score}%</b>
                <small>{match.decision}</small>
              </button>
            ))}
          </aside>

          <article className={styles.detailPanel}>
            <div className={styles.detailTop}>
              <div>
                <p className={styles.eyebrow}>
                  {selectedMatch.confidence} confidence · {selectedMatch.fit_band} fit
                </p>
                <h2>{selectedMatch.title}</h2>
                <p>
                  {selectedMatch.company_name} · {selectedMatch.location ?? "Location flexible"} ·{" "}
                  {salary(selectedMatch)}
                </p>
              </div>
              <div className={styles.scoreRing}>{selectedMatch.match_score}%</div>
            </div>

            <p className={styles.disclaimer}>{selectedMatch.summary}</p>

            <div className={styles.factorGrid}>
              {selectedMatch.breakdown.map((factor) => (
                <div className={styles.factor} key={factor.factor}>
                  <div>
                    <strong>{factor.factor.replaceAll("_", " ")}</strong>
                    <b>
                      {factor.score}/{factor.maximum}
                    </b>
                  </div>
                  <progress value={factor.score} max={factor.maximum} />
                  <p>{factor.reason}</p>
                </div>
              ))}
            </div>

            <div className={styles.twoColumns}>
              <div className={styles.goodPanel}>
                <h3>Why this deserves attention</h3>
                <ul>
                  {selectedMatch.strengths.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div className={styles.riskPanel}>
                <h3>What to address honestly</h3>
                <ul>
                  {selectedMatch.risks.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            <button
              className={styles.primaryButton}
              disabled={busy === "tailoring"}
              onClick={() => void openTailoring()}
            >
              {busy === "tailoring" ? "Opening resume studio…" : "Tailor my resume"}
              <ArrowRight size={18} />
            </button>
          </article>
        </section>
      ) : null}

      {stage === "tailoring" && tailoring ? (
        <section className={styles.singlePanel}>
          <div className={styles.panelHeading}>
            <div>
              <p className={styles.eyebrow}>Evidence-locked resume tailoring</p>
              <h2>
                Make your verified experience clearer for {tailoring.job_title}.
              </h2>
              <p>{tailoring.safety.message}</p>
            </div>
            <ShieldCheck size={36} />
          </div>

          <div className={styles.editList}>
            {tailoring.edits.map((edit) => (
              <article className={styles.editCard} key={edit.index}>
                <div className={styles.editHeader}>
                  <div>
                    <small>Edit {edit.index + 1}</small>
                    <h3>{edit.index === 0 ? "Recent experience" : edit.index === 1 ? "Professional summary" : "Role emphasis"}</h3>
                  </div>
                  <span className={styles.decision}>{edit.decision}</span>
                </div>
                <p className={styles.original}>
                  <strong>Original:</strong> {edit.current}
                </p>
                <label>
                  <span>Suggested language</span>
                  <textarea
                    value={edit.text}
                    onChange={(event) =>
                      updateTailoring(edit.index, { text: event.target.value })
                    }
                  />
                </label>
                <p className={styles.evidence}>
                  <ShieldCheck size={15} /> {edit.evidence}
                </p>
                <div className={styles.buttonRow}>
                  <button
                    className={styles.secondaryButton}
                    onClick={() => updateTailoring(edit.index, { decision: "REJECTED" })}
                  >
                    Reject
                  </button>
                  <button
                    className={styles.approveButton}
                    onClick={() => updateTailoring(edit.index, { decision: "APPROVED" })}
                  >
                    <Check size={16} /> Approve
                  </button>
                </div>
              </article>
            ))}
          </div>

          <button
            className={styles.primaryButton}
            disabled={busy === "finalize-resume"}
            onClick={() => void saveAndFinalizeResume()}
          >
            {busy === "finalize-resume"
              ? "Finalizing reviewed resume…"
              : "Finalize approved resume edits"}
            <ArrowRight size={18} />
          </button>
        </section>
      ) : null}

      {stage === "assistant" && assistant ? (
        <section className={styles.assistantLayout}>
          <article className={styles.singlePanel}>
            <div className={styles.panelHeading}>
              <div>
                <p className={styles.eyebrow}>Application assistant</p>
                <h2>Review every word before the package is marked ready.</h2>
                <p>{assistant.notice}</p>
              </div>
              <div className={styles.readiness}>{assistant.readiness_score}% ready</div>
            </div>

            <label className={styles.documentField}>
              <span>Cover letter draft</span>
              <textarea
                value={assistant.cover_letter}
                onChange={(event) =>
                  setAssistant({ ...assistant, cover_letter: event.target.value })
                }
              />
            </label>
            <label className={styles.verifyRow}>
              <input
                type="checkbox"
                checked={assistant.cover_letter_verified}
                onChange={(event) =>
                  setAssistant({
                    ...assistant,
                    cover_letter_verified: event.target.checked,
                  })
                }
              />
              I reviewed this cover letter and confirm it is accurate.
            </label>

            <div className={styles.questionList}>
              {assistant.questions.map((question, index) => (
                <article className={styles.questionCard} key={question.question}>
                  <h3>{question.question}</h3>
                  <textarea
                    value={question.answer}
                    onChange={(event) =>
                      updateQuestion(index, { answer: event.target.value })
                    }
                  />
                  <p className={styles.evidence}>
                    <ShieldCheck size={15} /> {question.evidence.join(" · ")}
                  </p>
                  <label className={styles.verifyRow}>
                    <input
                      type="checkbox"
                      checked={question.user_verified}
                      onChange={(event) =>
                        updateQuestion(index, {
                          user_verified: event.target.checked,
                        })
                      }
                    />
                    I reviewed and verified this answer.
                  </label>
                </article>
              ))}
            </div>
          </article>

          <aside className={styles.checklist}>
            <p className={styles.eyebrow}>Readiness checklist</p>
            <h2>Nothing is submitted automatically.</h2>
            {assistant.checklist.map((item) => (
              <div className={styles.checkItem} key={item.id}>
                {item.complete ? (
                  <CheckCircle2 className={styles.completeIcon} />
                ) : (
                  <span className={styles.emptyCheck} />
                )}
                <div>
                  <strong>{item.label}</strong>
                  <small>{item.weight}% of readiness</small>
                </div>
              </div>
            ))}
            <button
              className={styles.primaryButton}
              disabled={busy === "finalize-application"}
              onClick={() => void finalizeApplication()}
            >
              {busy === "finalize-application"
                ? "Finalizing application package…"
                : "Finalize reviewed package"}
              <FileCheck2 size={18} />
            </button>
          </aside>
        </section>
      ) : null}

      {stage === "complete" && finalPackage ? (
        <section className={styles.completePanel}>
          <div className={styles.completeIconLarge}>
            <CheckCircle2 />
          </div>
          <p className={styles.eyebrow}>Application package ready</p>
          <h2>Your reviewed materials are organized and ready to use.</h2>
          <p>{finalPackage.package_manifest}</p>
          <div className={styles.completeStats}>
            <div>
              <strong>{finalPackage.readiness_score}%</strong>
              <span>Candidate-reviewed</span>
            </div>
            <div>
              <strong>{finalPackage.current_status}</strong>
              <span>Tracker status</span>
            </div>
            <div>
              <strong>Required</strong>
              <span>External submission</span>
            </div>
          </div>
          <div className={styles.completeActions}>
            {finalPackage.source_url ? (
              <a
                className={styles.primaryButton}
                href={finalPackage.source_url}
                rel="noreferrer"
                target="_blank"
              >
                Open employer application
                <ArrowRight size={18} />
              </a>
            ) : null}
            <a className={styles.secondaryButton} href="/demo">
              Open application tracker
            </a>
          </div>
        </section>
      ) : null}

      <footer className={styles.footer}>
        <FileText size={16} />
        ApplyAI prepares truthful materials and organizes the workflow. You remain in control
        of every application.
      </footer>
    </main>
  );
}
