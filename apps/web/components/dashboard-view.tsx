"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  Circle,
  Eye,
  FileCheck2,
  Search,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Badge, Card, ErrorState, PageHeader } from "@/components/ui";
import { api, type CareerMatchV2 } from "@/lib/api/client";
import { resumeShareApi, type ResumeShareSnapshot } from "@/lib/api/resume-share";
import { formatDate, titleCase } from "@/lib/utils";

function matchLabel(decision?: string) {
  if (!decision) return "Worth a look";
  const normalized = decision.toUpperCase();
  if (normalized === "APPLY_NOW") return "Apply now";
  if (normalized === "STRONG") return "Strong fit";
  if (normalized === "CONSIDER") return "Worth considering";
  return titleCase(decision);
}

function firstEvidenceValue(match: CareerMatchV2 | undefined, keys: string[]) {
  if (!match) return null;
  for (const key of keys) {
    const value = match.evidence?.[key];
    if (Array.isArray(value)) {
      const first = value.find((item) => typeof item === "string" && item.trim());
      if (typeof first === "string") return first;
    }
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

function applicationEngagement(
  shares: ResumeShareSnapshot[],
  applicationId: string,
  jobId: string,
) {
  const linked = shares.filter(
    (share) => share.application_id === applicationId || share.job_id === jobId,
  );
  if (!linked.length) return null;
  const views = linked.reduce((sum, share) => sum + share.analytics.views, 0);
  const sessions = linked.flatMap((share) => share.analytics.sessions);
  const strongest = sessions.some((session) => session.intent === "DEEP_READ")
    ? "DEEP_READ"
    : sessions.some((session) => session.intent === "ENGAGED")
      ? "ENGAGED"
      : sessions.length
        ? "BROWSED"
        : null;
  const latest = sessions
    .map((session) => session.last_seen_at)
    .sort((a, b) => Date.parse(b) - Date.parse(a))[0];
  return { views, strongest, latest };
}

export function DashboardView() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const me = useQuery({ queryKey: ["me"], queryFn: ({ signal }) => api.auth.me(signal) });
  const profile = useQuery({
    queryKey: ["profile", "dashboard"],
    queryFn: ({ signal }) => api.profile.get(signal),
  });
  const resumes = useQuery({
    queryKey: ["resumes", "dashboard"],
    queryFn: ({ signal }) => api.resumes.list(signal),
  });
  const jobs = useQuery({
    queryKey: ["jobs", "dashboard"],
    queryFn: ({ signal }) => api.jobs.search(new URLSearchParams({ limit: "8" }), signal),
  });
  const matches = useQuery({
    queryKey: ["career-v2-matches", "dashboard"],
    queryFn: ({ signal }) => api.careerV2.matches(signal),
    retry: false,
  });
  const applications = useQuery({
    queryKey: ["applications", "dashboard"],
    queryFn: ({ signal }) => api.applications.list(signal),
  });
  const resumeShares = useQuery({
    queryKey: ["resume-shares", "dashboard"],
    queryFn: ({ signal }) => resumeShareApi.list(signal),
    retry: false,
  });

  useEffect(() => {
    if (me.data && !me.data.onboarding_completed) router.replace("/onboarding");
  }, [me.data, router]);

  const applicationItems = applications.data?.items ?? [];
  const matchByJob = useMemo(
    () => new Map((matches.data?.items ?? []).map((item) => [item.job_id, item])),
    [matches.data?.items],
  );
  const rankedJobs = useMemo(() => {
    const items = [...(jobs.data?.items ?? [])];
    return items.sort((left, right) => {
      const leftScore = matchByJob.get(left.id)?.final_score ?? -1;
      const rightScore = matchByJob.get(right.id)?.final_score ?? -1;
      return rightScore - leftScore;
    });
  }, [jobs.data?.items, matchByJob]);
  const topJob = rankedJobs[0];
  const topMatch = topJob ? matchByJob.get(topJob.id) : undefined;
  const activeApplication = applicationItems.find((item) =>
    !["REJECTED", "WITHDRAWN", "OFFER"].includes(item.current_status.toUpperCase()),
  );
  const latestResume = resumes.data?.[0];
  const resumeVerified = latestResume?.processing_status === "COMPLETED";
  const resumeNeedsReview = latestResume?.processing_status === "NEEDS_REVIEW";
  const profileReady = Boolean(
    profile.data?.target_roles?.length && profile.data?.work_modes?.length,
  );

  const nextAction = useMemo(() => {
    if (!latestResume) {
      return {
        kicker: "Build your evidence foundation",
        title: "Add your résumé before evaluating opportunities.",
        description:
          "ApplyAI uses your reviewed career evidence for matching, Recruiter Lens, tailoring, and interview preparation.",
        href: "/resume",
        label: "Upload résumé",
        icon: FileCheck2,
      };
    }
    if (resumeNeedsReview) {
      return {
        kicker: "Your review is needed",
        title: "Verify what ApplyAI extracted from your résumé.",
        description:
          "Parser output never becomes candidate truth until you review it. Confirm your experience and skills before using them elsewhere.",
        href: "/resume",
        label: "Review résumé",
        icon: FileCheck2,
      };
    }
    if (!profileReady) {
      return {
        kicker: "Set your career direction",
        title: "Tell ApplyAI which roles and work modes matter now.",
        description:
          "A focused target makes job recommendations and recruiter-fit analysis materially more useful.",
        href: "/career",
        label: "Finish career profile",
        icon: Target,
      };
    }
    if (activeApplication) {
      return {
        kicker: "Keep application momentum",
        title: `${activeApplication.job.title} at ${activeApplication.job.company_name}`,
        description: `${titleCase(activeApplication.current_status)} · continue the application, interview, or follow-up work already in progress.`,
        href: `/applications/${activeApplication.id}`,
        label: "Continue opportunity",
        icon: BriefcaseBusiness,
      };
    }
    if (topJob) {
      return {
        kicker: "Strongest opportunity to review",
        title: `${topJob.title} at ${topJob.company_name}`,
        description: topMatch
          ? `${matchLabel(topMatch.decision)} based on your verified profile and preferences. Open the role to inspect evidence and Recruiter Lens gaps.`
          : "A fresh role from your current search. Review the evidence before deciding whether it deserves your time.",
        href: `/jobs/${topJob.id}`,
        label: "Review role",
        icon: Sparkles,
      };
    }
    return {
      kicker: "Start your focused search",
      title: "Find the first opportunity worth preparing for.",
      description: "Browse current roles and ApplyAI will keep the strongest opportunities connected to your candidate evidence.",
      href: "/jobs",
      label: "Explore jobs",
      icon: Search,
    };
  }, [activeApplication, latestResume, profileReady, resumeNeedsReview, topJob, topMatch]);

  const readiness = [
    {
      label: "Résumé",
      ready: resumeVerified,
      detail: resumeVerified ? "Verified" : resumeNeedsReview ? "Needs review" : latestResume ? "Processing" : "Missing",
      href: "/resume",
    },
    {
      label: "Career profile",
      ready: profileReady,
      detail: profileReady ? "Ready" : "Finish targets",
      href: "/career",
    },
    {
      label: "Target roles",
      ready: Boolean(profile.data?.target_roles?.length),
      detail: profile.data?.target_roles?.length
        ? `${profile.data.target_roles.length} configured`
        : "Not configured",
      href: "/career",
    },
    {
      label: "Recruiter Lens",
      ready: Boolean(topJob && profileReady),
      detail: topJob && profileReady ? "Ready on matched roles" : "Needs profile + role",
      href: topJob ? `/jobs/${topJob.id}` : "/jobs",
    },
  ];
  const readinessCount = readiness.filter((item) => item.ready).length;

  if (
    me.isError ||
    profile.isError ||
    resumes.isError ||
    jobs.isError ||
    applications.isError
  ) {
    return <ErrorState retry={() => location.reload()} />;
  }

  const NextIcon = nextAction.icon;

  return (
    <>
      <PageHeader
        eyebrow="Home"
        title="Your career workspace is ready."
        description="One place to decide what deserves your attention, strengthen the evidence, and keep every active opportunity moving."
      />

      <section className="first-value-next" aria-labelledby="next-best-action">
        <Card className="first-value-next-card">
          <span className="first-value-next-icon"><NextIcon size={22} aria-hidden="true" /></span>
          <div className="first-value-next-copy">
            <p className="eyebrow">{nextAction.kicker}</p>
            <h2 id="next-best-action">{nextAction.title}</h2>
            <p>{nextAction.description}</p>
          </div>
          <Link className="ui-button ui-button-primary" href={nextAction.href}>
            {nextAction.label} <ArrowRight size={16} />
          </Link>
        </Card>
      </section>

      <div className="first-value-grid">
        <section className="first-value-main" aria-labelledby="jobs-for-you">
          <div className="cx-section-heading">
            <div>
              <p className="eyebrow">Jobs for you</p>
              <h2 id="jobs-for-you">Opportunities worth inspecting</h2>
            </div>
            <Link href="/jobs" className="text-button">View all jobs <ArrowRight size={14} /></Link>
          </div>

          <div className="first-value-job-list">
            {jobs.isLoading ? (
              <Card className="first-value-loading">
                <Sparkles size={20} />
                <div><strong>Building your shortlist</strong><span>Checking current roles against your verified profile and preferences.</span></div>
              </Card>
            ) : rankedJobs.length ? (
              rankedJobs.slice(0, 4).map((job) => {
                const match = matchByJob.get(job.id);
                const support = firstEvidenceValue(match, ["matched_skills", "strengths", "supporting_evidence"]);
                const gap = firstEvidenceValue(match, ["missing_skills", "gaps", "risks"]);
                return (
                  <Link className="first-value-job" href={`/jobs/${job.id}`} key={job.id}>
                    <div className="first-value-job-topline">
                      <div>
                        <strong>{job.title}</strong>
                        <span>{job.company_name} · {job.location ?? "Location flexible"}</span>
                      </div>
                      {match ? <Badge tone="success">Match {Math.round(match.final_score)}/100</Badge> : <Badge tone="info">Fresh role</Badge>}
                    </div>
                    <div className="first-value-job-evidence">
                      <span><CheckCircle2 size={14} />{support ?? (match ? `${matchLabel(match.decision)} · ${titleCase(match.fit_band)} fit` : "Review role evidence")}</span>
                      <span><Circle size={14} />{gap ?? "Open Recruiter Lens to inspect evidence gaps"}</span>
                    </div>
                    <ArrowRight className="first-value-job-arrow" size={18} />
                  </Link>
                );
              })
            ) : (
              <Card className="first-value-empty">
                <Search size={20} />
                <div><strong>No recommendation set yet</strong><span>Browse the current inventory while ApplyAI builds your candidate-specific shortlist.</span></div>
                <Link className="text-button" href="/jobs">Explore jobs</Link>
              </Card>
            )}
          </div>
        </section>

        <aside className="first-value-readiness" aria-labelledby="career-readiness">
          <Card>
            <div className="first-value-readiness-head">
              <div><p className="eyebrow">Career readiness</p><h2 id="career-readiness">{readinessCount}/{readiness.length} foundations ready</h2></div>
              <Target size={21} aria-hidden="true" />
            </div>
            <p className="first-value-readiness-note">This measures preparation workflow completion, not employer interest or hiring probability.</p>
            <div className="first-value-checklist">
              {readiness.map((item) => (
                <Link href={item.href} key={item.label}>
                  {item.ready ? <CheckCircle2 size={17} /> : <Circle size={17} />}
                  <span><strong>{item.label}</strong><small>{item.detail}</small></span>
                  <ArrowRight size={14} />
                </Link>
              ))}
            </div>
          </Card>
        </aside>
      </div>

      <section className="first-value-opportunities" aria-labelledby="active-opportunities">
        <div className="cx-section-heading">
          <div><p className="eyebrow">Active opportunities</p><h2 id="active-opportunities">Keep the pipeline moving</h2></div>
          <Link href="/applications" className="text-button">All applications <ArrowRight size={14} /></Link>
        </div>
        {applicationItems.length ? (
          <div className="first-value-opportunity-list">
            {applicationItems.slice(0, 4).map((application) => {
              const engagement = applicationEngagement(
                resumeShares.data ?? [],
                application.id,
                application.job.id,
              );
              return (
                <Card className="first-value-opportunity" key={application.id}>
                  <div className="first-value-opportunity-main">
                    <span className="first-value-opportunity-icon"><BriefcaseBusiness size={18} /></span>
                    <div>
                      <strong>{application.job.title}</strong>
                      <span>{application.job.company_name} · {titleCase(application.current_status)}</span>
                    </div>
                  </div>
                  {engagement?.views ? (
                    <div className="first-value-engagement">
                      <Eye size={16} />
                      <div>
                        <strong>{engagement.strongest ? titleCase(engagement.strongest) : "Viewed"}</strong>
                        <span>{engagement.views} tracked view{engagement.views === 1 ? "" : "s"}{engagement.latest ? ` · last ${formatDate(engagement.latest)}` : ""}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="first-value-engagement muted">
                      <Eye size={16} />
                      <span>No tracked résumé engagement yet</span>
                    </div>
                  )}
                  <Link className="ui-button ui-button-secondary" href={`/applications/${application.id}`}>
                    Open workspace <ArrowRight size={15} />
                  </Link>
                </Card>
              );
            })}
          </div>
        ) : (
          <Card className="first-value-empty">
            <BriefcaseBusiness size={20} />
            <div><strong>No active applications yet</strong><span>Choose a role worth pursuing and its preparation, outreach, interview work, and follow-up will stay connected here.</span></div>
            <Link className="text-button" href="/jobs">Find a role</Link>
          </Card>
        )}
        <p className="first-value-engagement-disclaimer">
          Resume-share activity reports observed engagement only. A view or Deep Read is not recruiter approval, interview selection, or hiring probability.
        </p>
      </section>

      <Card className="cx-search-strip">
        <div><strong>Looking for something specific?</strong><span>Search by title, skill, or company.</span></div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            router.push(query ? `/jobs?keyword=${encodeURIComponent(query)}` : "/jobs");
          }}
        >
          <input className="ui-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. Data Engineering Manager" aria-label="Search jobs" />
          <button className="ui-button ui-button-primary" type="submit"><Search size={17} />Search</button>
        </form>
      </Card>
    </>
  );
}
