"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  FileText,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, Textarea } from "@/components/ui";
import { api, type AIJobRun } from "@/lib/api/client";
import {
  careerSystemApi,
  type CareerSystemCommunicationWrite,
} from "@/lib/api/career-system";
import { titleCase } from "@/lib/utils";
import styles from "./career-system-panel.module.css";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForRun(run: AIJobRun): Promise<AIJobRun> {
  let current = run;
  for (let attempt = 0; attempt < 45; attempt += 1) {
    if (current.status === "COMPLETED") return current;
    if (current.status === "FAILED") {
      throw new Error(current.error_code || "Interview preparation failed");
    }
    await sleep(1000);
    current = await api.careerV2.run(current.id);
  }
  return current;
}

export function CareerSystemPanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const system = useQuery({
    queryKey: ["career-system", jobId],
    queryFn: ({ signal }) => careerSystemApi.get(jobId, signal),
  });
  const [communicationsDraft, setCommunicationsDraft] =
    useState<CareerSystemCommunicationWrite | null>(null);

  const saveCommunications = useMutation({
    mutationFn: (payload: CareerSystemCommunicationWrite) =>
      careerSystemApi.saveCommunications(jobId, payload),
    onSuccess: (data) => {
      setCommunicationsDraft(null);
      queryClient.setQueryData(["career-system", jobId], data);
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      toast.success("Recruiter outreach and follow-up saved");
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "We couldn't save those messages.",
      ),
  });

  const startApplication = useMutation({
    mutationFn: () => api.applications.create(jobId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["career-system", jobId] });
      await queryClient.invalidateQueries({ queryKey: ["applications"] });
      toast.success("Application workspace started");
    },
    onError: () => toast.error("We couldn't start the application workspace."),
  });

  const prepareInterview = useMutation({
    mutationFn: async () =>
      waitForRun(await api.careerV2.start(jobId, "interview-prep")),
    onSuccess: async (run) => {
      await queryClient.invalidateQueries({ queryKey: ["career-system", jobId] });
      toast.success(
        run.status === "COMPLETED"
          ? "Job-specific interview preparation is ready"
          : "Interview preparation is processing",
      );
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "We couldn't prepare the interview pack.",
      ),
  });

  if (system.isLoading) {
    return (
      <Card className={styles.panel}>
        <p className="muted">Building your Career System for this role…</p>
      </Card>
    );
  }
  if (system.isError || !system.data) {
    return (
      <Card className={styles.panel}>
        <p className="field-error">
          {system.error instanceof Error
            ? system.error.message
            : "Career System is unavailable."}
        </p>
        <Button size="small" variant="secondary" onClick={() => system.refetch()}>
          Try again
        </Button>
      </Card>
    );
  }

  const item = system.data;
  const serverCommunications: CareerSystemCommunicationWrite = {
    recruiter_message: item.communications.recruiter_message,
    recruiter_message_verified: item.communications.recruiter_message_verified,
    follow_up_message: item.communications.follow_up_message,
    follow_up_message_verified: item.communications.follow_up_message_verified,
  };
  const communications = communicationsDraft ?? serverCommunications;
  const incomplete = item.stages.filter((stage) => !stage.complete);
  const communicationChanged =
    communicationsDraft !== null &&
    (communications.recruiter_message !== serverCommunications.recruiter_message ||
      communications.follow_up_message !== serverCommunications.follow_up_message ||
      communications.recruiter_message_verified !==
        serverCommunications.recruiter_message_verified ||
      communications.follow_up_message_verified !==
        serverCommunications.follow_up_message_verified);

  function updateCommunications(patch: Partial<CareerSystemCommunicationWrite>) {
    setCommunicationsDraft({ ...communications, ...patch });
  }

  return (
    <Card className={styles.panel}>
      <div className={styles.header}>
        <div>
          <p className="eyebrow">Career System</p>
          <h2>One role. One complete application workspace.</h2>
          <p>
            Resume intelligence, fit, application materials, outreach, portfolio positioning,
            interview preparation, and application progress stay connected here.
          </p>
        </div>
        <div
          className={styles.progress}
          aria-label={`${item.progress_score}% preparation complete`}
        >
          <strong>{item.progress_score}%</strong>
          <span>prepared</span>
        </div>
      </div>

      <div className={styles.progressTrack} aria-hidden="true">
        <span style={{ width: `${item.progress_score}%` }} />
      </div>
      <p className={styles.explanation}>{item.progress_explanation}</p>

      <div className={styles.stageGrid}>
        {item.stages.map((stage) => (
          <div className={styles.stage} key={stage.id}>
            <CheckCircle2
              size={16}
              className={stage.complete ? styles.complete : styles.incomplete}
            />
            <span>{stage.label}</span>
          </div>
        ))}
      </div>

      {item.next_action ? (
        <div className={styles.nextAction}>
          <div>
            <span>Next best action</span>
            <strong>{item.next_action.label}</strong>
          </div>
          <Badge tone="info">{100 - item.progress_score}% remaining</Badge>
        </div>
      ) : (
        <div className={styles.nextAction}>
          <div>
            <span>Preparation status</span>
            <strong>Your job-search system is complete for this role.</strong>
          </div>
          <Badge tone="success">Ready</Badge>
        </div>
      )}

      <div className={styles.grid}>
        <section className={styles.section}>
          <div className={styles.sectionTitle}>
            <FileText size={19} />
            <div>
              <h3>Resume + fit</h3>
              <p>Verified evidence against this role.</p>
            </div>
          </div>
          <div className={styles.metrics}>
            <div>
              <strong>{item.match.match_score}%</strong>
              <span>fit score</span>
            </div>
            <div>
              <strong>{item.match.matched_skills.length}</strong>
              <span>matched skills</span>
            </div>
            <div>
              <strong>{item.match.missing_skills.length}</strong>
              <span>skill gaps</span>
            </div>
          </div>
          <div className={styles.badges}>
            <Badge tone={item.resume.ready ? "success" : "warning"}>
              {item.resume.ready ? "Resume processed" : "Resume needs attention"}
            </Badge>
            <Badge tone="info">{titleCase(item.match.decision)}</Badge>
            <Badge>{titleCase(item.match.confidence)} confidence</Badge>
          </div>
          {item.match.missing_skills.length ? (
            <p className={styles.compactCopy}>
              Gaps to address honestly: {item.match.missing_skills.slice(0, 5).join(", ")}.
            </p>
          ) : null}
          <Link className={styles.link} href="/resume/studio">
            Open resume studio <ArrowRight size={14} />
          </Link>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionTitle}>
            <BriefcaseBusiness size={19} />
            <div>
              <h3>Application package</h3>
              <p>Resume, cover letter, and application answers.</p>
            </div>
          </div>
          <div className={styles.metrics}>
            <div>
              <strong>{item.application_package.readiness_score}%</strong>
              <span>package ready</span>
            </div>
            <div>
              <strong>
                {item.application_package.verified_question_count}/
                {item.application_package.question_count}
              </strong>
              <span>answers reviewed</span>
            </div>
          </div>
          <div className={styles.badges}>
            <Badge
              tone={
                item.application_package.cover_letter_verified ? "success" : "warning"
              }
            >
              {item.application_package.cover_letter_verified
                ? "Cover letter reviewed"
                : "Cover letter needs review"}
            </Badge>
            {item.application_status ? (
              <Badge>{titleCase(item.application_status)}</Badge>
            ) : null}
          </div>
          {item.application_id ? (
            <Link className={styles.link} href={`/applications/${item.application_id}`}>
              Open application workspace <ArrowRight size={14} />
            </Link>
          ) : (
            <Button
              size="small"
              onClick={() => startApplication.mutate()}
              disabled={startApplication.isPending}
            >
              {startApplication.isPending ? "Starting…" : "Start application workspace"}
            </Button>
          )}
        </section>
      </div>

      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <MessageSquareText size={19} />
          <div>
            <h3>Recruiter outreach + follow-up</h3>
            <p>
              Drafted from this role and your verified profile. Edit freely, then mark each as
              reviewed.
            </p>
          </div>
        </div>
        <div className={styles.messageGrid}>
          <div className={styles.messageField}>
            <label htmlFor="career-system-recruiter-message">Recruiter message</label>
            <Textarea
              id="career-system-recruiter-message"
              value={communications.recruiter_message}
              onChange={(event) =>
                updateCommunications({
                  recruiter_message: event.target.value,
                  recruiter_message_verified: false,
                })
              }
              rows={6}
            />
            <label className={styles.checkRow}>
              <input
                type="checkbox"
                checked={communications.recruiter_message_verified}
                onChange={(event) =>
                  updateCommunications({
                    recruiter_message_verified: event.target.checked,
                  })
                }
              />
              I reviewed this message and the claims are accurate.
            </label>
          </div>
          <div className={styles.messageField}>
            <label htmlFor="career-system-follow-up-message">Post-application follow-up</label>
            <Textarea
              id="career-system-follow-up-message"
              value={communications.follow_up_message}
              onChange={(event) =>
                updateCommunications({
                  follow_up_message: event.target.value,
                  follow_up_message_verified: false,
                })
              }
              rows={6}
            />
            <label className={styles.checkRow}>
              <input
                type="checkbox"
                checked={communications.follow_up_message_verified}
                onChange={(event) =>
                  updateCommunications({
                    follow_up_message_verified: event.target.checked,
                  })
                }
              />
              I reviewed this follow-up and the claims are accurate.
            </label>
          </div>
        </div>
        <div className={styles.actions}>
          <Button
            size="small"
            disabled={
              !communicationChanged ||
              !communications.recruiter_message.trim() ||
              !communications.follow_up_message.trim() ||
              saveCommunications.isPending
            }
            onClick={() => saveCommunications.mutate(communications)}
          >
            <ShieldCheck size={15} />
            {saveCommunications.isPending ? "Saving…" : "Save reviewed messages"}
          </Button>
          <Badge tone="warning">Candidate review required before sending</Badge>
        </div>
      </section>

      <div className={styles.grid}>
        <section className={styles.section}>
          <div className={styles.sectionTitle}>
            <UserRound size={19} />
            <div>
              <h3>Portfolio / professional profile preview</h3>
              <p>Reusable positioning from verified evidence only.</p>
            </div>
          </div>
          <div className={styles.portfolio}>
            <strong>{item.portfolio_preview.headline}</strong>
            <p>{item.portfolio_preview.about}</p>
            {item.portfolio_preview.highlights.slice(0, 2).map((highlight) => (
              <div key={`${highlight.company}-${highlight.title}`}>
                <span>
                  {highlight.title} · {highlight.company}
                </span>
                {highlight.description ? <p>{highlight.description}</p> : null}
              </div>
            ))}
          </div>
          <div className={styles.badges}>
            {item.portfolio_preview.skills.slice(0, 6).map((skill) => (
              <Badge key={skill}>{skill}</Badge>
            ))}
          </div>
          <Link className={styles.link} href="/career">
            Strengthen career evidence <ArrowRight size={14} />
          </Link>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionTitle}>
            <Sparkles size={19} />
            <div>
              <h3>Interview preparation</h3>
              <p>Job-specific questions grounded in fit evidence.</p>
            </div>
          </div>
          {item.interview.ready ? (
            <>
              <Badge tone={item.interview.candidate_verified ? "success" : "info"}>
                {item.interview.candidate_verified
                  ? "Interview pack reviewed"
                  : "Interview pack ready"}
              </Badge>
              <p className={styles.compactCopy}>
                ApplyAI has generated a full evidence-bound interview-preparation artifact for
                this role.
              </p>
            </>
          ) : (
            <div className={styles.questions}>
              {item.interview.starter_questions.slice(0, 4).map((question) => (
                <div key={`${question.focus}-${question.question}`}>
                  <span>{question.focus}</span>
                  <p>{question.question}</p>
                </div>
              ))}
            </div>
          )}
          <Button
            size="small"
            variant={item.interview.ready ? "secondary" : "primary"}
            onClick={() => prepareInterview.mutate()}
            disabled={prepareInterview.isPending}
          >
            <Sparkles size={15} />
            {prepareInterview.isPending
              ? "Preparing…"
              : item.interview.ready
                ? "Refresh interview pack"
                : "Create full interview pack"}
          </Button>
        </section>
      </div>

      {incomplete.length ? (
        <div className={styles.footerNote}>
          <ShieldCheck size={17} />
          <span>
            ApplyAI can prepare and automate workflows, but candidate review remains the
            authority for claims, sensitive answers, outreach, and external submission.
          </span>
        </div>
      ) : null}
    </Card>
  );
}
