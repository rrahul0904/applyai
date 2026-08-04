"use client";

import {
  ArrowLeft,
  ArrowRight,
  Bookmark,
  BriefcaseBusiness,
  Check,
  CircleDollarSign,
  FileText,
  Home,
  MapPin,
  Menu,
  RefreshCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  api,
  type ApplicationListItem,
  type Profile,
  type ProfileWrite,
} from "@/lib/api/client";
import styles from "./functional-demo.module.css";

type View = "today" | "matches" | "resume" | "tracker";
type Phase = "loading" | "ready" | "auth" | "error";
type Decision = "PENDING" | "APPROVED" | "REJECTED";

type Recommendation = {
  id: string;
  title: string;
  company_name: string;
  location: string | null;
  work_mode: string | null;
  minimum_compensation: number | null;
  maximum_compensation: number | null;
  posted_at: string | null;
  last_seen_at: string;
  saved: boolean;
  match_score: number;
  summary: string;
  strengths: string[];
  gaps: string[];
  skills: string[];
  source_label: string;
  data_origin: string;
};

type RecommendationResponse = {
  profile_ready: boolean;
  search_goal: {
    target_roles: string[];
    location_text: string | null;
    work_modes: string[];
    minimum_compensation: number | null;
  };
  items: Recommendation[];
};

type TailoringEdit = {
  index: number;
  current: string;
  suggested: string;
  evidence: string;
  text: string;
  decision: Decision;
};

type TailoringResponse = {
  job_id: string;
  application_id: string | null;
  job_title: string;
  company_name: string;
  edits: TailoringEdit[];
};

type PreferenceDraft = {
  targetRoles: string;
  location: string;
  minimumCompensation: string;
  remote: boolean;
  hybrid: boolean;
};

const DEMO_PROFILE: ProfileWrite = {
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
        "Modernized AWS and Snowflake data platforms, introduced dbt standards, and partnered with product and analytics leaders on a three-year roadmap.",
      provenance: "USER_VERIFIED",
    },
  ],
  education: [],
  skills: [
    { name: "Python", provenance: "USER_VERIFIED" },
    { name: "SQL", provenance: "USER_VERIFIED" },
    { name: "AWS", provenance: "USER_VERIFIED" },
    { name: "Snowflake", provenance: "USER_VERIFIED" },
    { name: "Analytics", provenance: "USER_VERIFIED" },
    { name: "Machine learning", provenance: "USER_VERIFIED" },
    { name: "Data architecture", provenance: "USER_VERIFIED" },
    { name: "People leadership", provenance: "USER_VERIFIED" },
  ],
};

const navigation: Array<{ id: View; label: string; icon: typeof Home }> = [
  { id: "today", label: "Today", icon: Home },
  { id: "matches", label: "Best matches", icon: Target },
  { id: "resume", label: "Resume studio", icon: FileText },
  { id: "tracker", label: "Applications", icon: BriefcaseBusiness },
];

const statusColumns = [
  { id: "PREPARING", label: "Preparing" },
  { id: "APPLIED", label: "Applied" },
  { id: "INTERVIEW", label: "Interviewing" },
  { id: "OFFER", label: "Offer" },
] as const;

const statusProgression = ["PREPARING", "APPLIED", "INTERVIEW", "OFFER"];

async function workspaceRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend/workspace${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: { code?: string; message?: string } }
      | null;
    throw new Error(payload?.error?.message ?? "The candidate workspace request failed.");
  }
  return response.json() as Promise<T>;
}

function initials(company: string) {
  return company
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function compensation(job: Recommendation) {
  const minimum = job.minimum_compensation;
  const maximum = job.maximum_compensation;
  if (minimum == null && maximum == null) return "Salary not listed";
  const format = (value: number) =>
    value >= 1000 ? `$${Math.round(value / 1000)}K` : `$${value.toLocaleString()}`;
  if (minimum != null && maximum != null) return `${format(minimum)}–${format(maximum)}`;
  if (minimum != null) return `${format(minimum)}+`;
  return `Up to ${format(maximum as number)}`;
}

function relativePosting(job: Recommendation) {
  const raw = job.posted_at ?? job.last_seen_at;
  const time = new Date(raw).getTime();
  if (!Number.isFinite(time)) return "Recently verified";
  const days = Math.max(0, Math.round((Date.now() - time) / 86_400_000));
  if (days === 0) return "Posted today";
  if (days === 1) return "Posted yesterday";
  return `Posted ${days} days ago`;
}

function applicationBucket(status: string) {
  if (["RECRUITER_SCREEN", "ASSESSMENT", "INTERVIEW", "FINAL_INTERVIEW"].includes(status)) {
    return "INTERVIEW";
  }
  if (status === "READY") return "PREPARING";
  return status;
}

export function FunctionalCandidateDemo() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [tailoring, setTailoring] = useState<TailoringResponse | null>(null);
  const [view, setView] = useState<View>("today");
  const [query, setQuery] = useState("");
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const notify = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2400);
  }, []);

  const loadWorkspace = useCallback(async () => {
    const [profileResponse, recommendationResponse, applicationsResponse] =
      await Promise.all([
        api.profile.get(),
        workspaceRequest<RecommendationResponse>("/recommendations?limit=30"),
        api.applications.list(),
      ]);
    setProfile(profileResponse);
    setRecommendations(recommendationResponse.items);
    setApplications(applicationsResponse.items);
    setSelectedJobId((current) => current ?? recommendationResponse.items[0]?.id ?? null);
  }, []);

  const initialize = useCallback(async () => {
    setPhase("loading");
    setError(null);
    try {
      try {
        await api.auth.me();
      } catch (authError) {
        if (!(authError instanceof ApiError) || authError.status !== 401) throw authError;
        const sessionResponse = await fetch("/api/demo-session", { method: "POST" });
        if (!sessionResponse.ok) {
          setPhase("auth");
          return;
        }
        await api.auth.me();
      }

      let currentProfile = await api.profile.get();
      if (!currentProfile) currentProfile = await api.profile.save(DEMO_PROFILE);
      setProfile(currentProfile);
      await loadWorkspace();
      setPhase("ready");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The workspace could not be loaded.");
      setPhase("error");
    }
  }, [loadWorkspace]);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  const visibleRecommendations = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return recommendations;
    return recommendations.filter((job) =>
      [job.title, job.company_name, job.location ?? "", ...job.skills]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [query, recommendations]);

  const selectedJob = useMemo(
    () =>
      recommendations.find((job) => job.id === selectedJobId) ??
      recommendations[0] ??
      null,
    [recommendations, selectedJobId],
  );

  const applicationByJob = useMemo(
    () => new Map(applications.map((application) => [application.job_id, application])),
    [applications],
  );

  const navigate = (next: View) => {
    setView(next);
    setMobileMenuOpen(false);
  };

  const refresh = async (message?: string) => {
    setBusy("refresh");
    try {
      await loadWorkspace();
      if (message) notify(message);
    } finally {
      setBusy(null);
    }
  };

  const toggleSaved = async (job: Recommendation) => {
    setBusy(`save:${job.id}`);
    try {
      if (job.saved) await api.savedJobs.unsave(job.id);
      else await api.savedJobs.save(job.id);
      await refresh(job.saved ? "Removed from saved jobs" : "Job saved");
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : "The job could not be saved.");
    } finally {
      setBusy(null);
    }
  };

  const openJob = (jobId: string) => {
    setSelectedJobId(jobId);
    setView("matches");
  };

  const openTailoring = async () => {
    if (!selectedJob) return;
    setBusy("tailoring");
    try {
      const response = await workspaceRequest<TailoringResponse>(
        `/tailoring/${selectedJob.id}`,
      );
      setTailoring(response);
      setView("resume");
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : "Resume tailoring could not be loaded.");
    } finally {
      setBusy(null);
    }
  };

  const createApplication = async (jobId: string) => {
    setBusy(`application:${jobId}`);
    try {
      await api.applications.create(jobId);
      await refresh("Added to your application plan");
      setView("tracker");
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : "The application could not be created.");
    } finally {
      setBusy(null);
    }
  };

  const updateStatus = async (application: ApplicationListItem, status: string) => {
    setBusy(`status:${application.id}`);
    try {
      await api.applications.updateStatus(application.id, status);
      await refresh("Application stage updated");
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : "The application stage could not be updated.");
    } finally {
      setBusy(null);
    }
  };

  const saveTailoring = async (goToTracker: boolean) => {
    if (!tailoring) return;
    setBusy("save-tailoring");
    try {
      const saved = await workspaceRequest<TailoringResponse>(
        `/tailoring/${tailoring.job_id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            edits: tailoring.edits.map((edit) => ({
              index: edit.index,
              text: edit.text,
              decision: edit.decision,
            })),
          }),
        },
      );
      setTailoring(saved);
      await loadWorkspace();
      notify("Resume decisions saved to the application");
      if (goToTracker) setView("tracker");
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : "Resume decisions could not be saved.");
    } finally {
      setBusy(null);
    }
  };

  const savePreferences = async (draft: PreferenceDraft) => {
    if (!profile) return;
    setBusy("preferences");
    try {
      const payload: ProfileWrite = {
        headline: profile.headline,
        current_title: profile.current_title,
        summary: profile.summary,
        years_experience: profile.years_experience,
        target_roles: draft.targetRoles
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        location_text: draft.location.trim() || null,
        work_modes: [draft.remote ? "REMOTE" : null, draft.hybrid ? "HYBRID" : null].filter(
          (value): value is string => Boolean(value),
        ),
        minimum_compensation: Number(draft.minimumCompensation) || null,
        experiences: profile.experiences,
        education: profile.education,
        skills: profile.skills,
      };
      await api.profile.save(payload);
      setPreferencesOpen(false);
      await refresh("Matches re-ranked for your new goals");
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : "Preferences could not be saved.");
    } finally {
      setBusy(null);
    }
  };

  const toggleCompare = (jobId: string) => {
    setCompareIds((current) => {
      if (current.includes(jobId)) return current.filter((id) => id !== jobId);
      if (current.length === 2) {
        notify("Compare up to two jobs at a time");
        return current;
      }
      return [...current, jobId];
    });
  };

  if (phase !== "ready") {
    return (
      <main className={styles.loadingShell}>
        <section className={styles.loadingCard}>
          <span className={styles.eyebrow}>ApplyAI functional workspace</span>
          {phase === "loading" ? (
            <>
              <h1>Preparing your real candidate workspace.</h1>
              <p>
                ApplyAI is loading the saved profile, database jobs, recommendations,
                application history, and resume decisions.
              </p>
              <div className={styles.progress}><div /></div>
            </>
          ) : phase === "auth" ? (
            <>
              <h1>Sign in to use the functional workspace.</h1>
              <p>
                The account-free identity is limited to local and test environments.
                In a deployed environment, use the normal ApplyAI sign-in.
              </p>
              <a className={`${styles.button} ${styles.primary}`} href="/">
                Go to ApplyAI sign-in
              </a>
            </>
          ) : (
            <>
              <h1>The workspace did not load.</h1>
              <div className={styles.errorBox}>{error}</div>
              <button className={`${styles.button} ${styles.primary}`} onClick={() => void initialize()}>
                <RefreshCcw size={17} /> Retry
              </button>
            </>
          )}
        </section>
      </main>
    );
  }

  const goalTitle = profile?.target_roles?.[0] ?? "Focused job search";
  const goalSummary = [
    profile?.location_text,
    profile?.work_modes?.join(" / "),
    profile?.minimum_compensation
      ? `$${Math.round(profile.minimum_compensation / 1000)}K+`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <main className={styles.shell}>
      <aside className={`${styles.sidebar} ${mobileMenuOpen ? styles.sidebarOpen : ""}`}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>A</span>
          ApplyAI
        </div>
        <div className={styles.profileCard}>
          <div className={styles.avatar}>AM</div>
          <div className={styles.profileCopy}>
            <strong>Alex Morgan</strong>
            <span>{profile?.current_title ?? "Candidate"}</span>
          </div>
        </div>
        <nav className={styles.nav} aria-label="Candidate workspace navigation">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button
                type="button"
                key={item.id}
                className={`${styles.navButton} ${view === item.id ? styles.navButtonActive : ""}`}
                onClick={() => navigate(item.id)}
                aria-current={view === item.id ? "page" : undefined}
              >
                <Icon size={18} />
                {item.label}
                {item.id === "tracker" ? (
                  <span className={styles.navCount}>{applications.length}</span>
                ) : null}
              </button>
            );
          })}
        </nav>
        <div className={styles.goalCard}>
          <span>Search goal</span>
          <strong>{goalTitle}</strong>
          <small>{goalSummary}</small>
          <button type="button" onClick={() => setPreferencesOpen(true)}>
            Edit preferences
          </button>
        </div>
      </aside>

      {mobileMenuOpen ? (
        <button
          className={styles.mobileOverlay}
          aria-label="Close navigation"
          onClick={() => setMobileMenuOpen(false)}
        />
      ) : null}

      <section className={styles.workspace}>
        <header className={styles.topbar}>
          <button
            type="button"
            className={styles.menuButton}
            onClick={() => setMobileMenuOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>
          <label className={styles.searchBox}>
            <Search size={18} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search your ranked jobs"
              aria-label="Search your ranked jobs"
            />
          </label>
          <span className={styles.demoPill}>
            <Sparkles size={15} /> Real API + PostgreSQL
          </span>
        </header>

        <div className={styles.page}>
          {view === "today" ? (
            <TodayView
              jobs={visibleRecommendations.slice(0, 6)}
              profile={profile}
              compareIds={compareIds}
              busy={busy}
              onOpen={openJob}
              onSave={(job) => void toggleSaved(job)}
              onCompare={toggleCompare}
              onViewAll={() => navigate("matches")}
            />
          ) : null}

          {view === "matches" ? (
            <MatchesView
              jobs={visibleRecommendations}
              selectedJob={selectedJob}
              compareIds={compareIds}
              applicationByJob={applicationByJob}
              busy={busy}
              onSelect={setSelectedJobId}
              onSave={(job) => void toggleSaved(job)}
              onCompare={toggleCompare}
              onTailor={() => void openTailoring()}
              onApplication={(jobId) => void createApplication(jobId)}
            />
          ) : null}

          {view === "resume" ? (
            <ResumeView
              profile={profile}
              tailoring={tailoring}
              busy={busy}
              onBack={() => navigate("matches")}
              onChange={(edits) =>
                setTailoring((current) => (current ? { ...current, edits } : current))
              }
              onSave={(toTracker) => void saveTailoring(toTracker)}
            />
          ) : null}

          {view === "tracker" ? (
            <TrackerView
              applications={applications}
              busy={busy}
              onStatus={(application, status) => void updateStatus(application, status)}
              onOpenJob={openJob}
            />
          ) : null}
        </div>
      </section>

      {preferencesOpen && profile ? (
        <PreferencesModal
          profile={profile}
          busy={busy === "preferences"}
          onClose={() => setPreferencesOpen(false)}
          onSave={(draft) => void savePreferences(draft)}
        />
      ) : null}

      {compareIds.length ? (
        <div className={styles.compareBar}>
          <strong>Compare jobs</strong>
          <div className={styles.compareItems}>
            {compareIds.map((id) => {
              const job = recommendations.find((item) => item.id === id);
              return job ? (
                <span key={id} className={styles.compareTag}>
                  {job.company_name} · {job.match_score}%
                </span>
              ) : null;
            })}
          </div>
          <button className={`${styles.button} ${styles.secondary}`} onClick={() => setCompareIds([])}>
            Clear
          </button>
          <button
            className={`${styles.button} ${styles.primary}`}
            disabled={compareIds.length !== 2}
            onClick={() => setCompareOpen(true)}
          >
            Compare {compareIds.length}/2
          </button>
        </div>
      ) : null}

      {compareOpen ? (
        <CompareModal
          jobs={compareIds
            .map((id) => recommendations.find((item) => item.id === id))
            .filter((job): job is Recommendation => Boolean(job))}
          onClose={() => setCompareOpen(false)}
          onOpen={(id) => {
            setCompareOpen(false);
            openJob(id);
          }}
        />
      ) : null}

      {toast ? <div className={styles.toast}>{toast}</div> : null}
    </main>
  );
}

function TodayView({
  jobs,
  profile,
  compareIds,
  busy,
  onOpen,
  onSave,
  onCompare,
  onViewAll,
}: {
  jobs: Recommendation[];
  profile: Profile | null;
  compareIds: string[];
  busy: string | null;
  onOpen: (id: string) => void;
  onSave: (job: Recommendation) => void;
  onCompare: (id: string) => void;
  onViewAll: () => void;
}) {
  const top = jobs[0];
  const compensationMatches = jobs.filter(
    (job) =>
      !profile?.minimum_compensation ||
      (job.maximum_compensation ?? 0) >= profile.minimum_compensation,
  ).length;
  return (
    <div className={styles.stack}>
      <section className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>Your real job search, prioritized</span>
          <h1>Good afternoon, Alex.</h1>
          <p>
            These roles were loaded from ApplyAI’s job database and ranked against
            your saved profile, location, work preferences, skills, and compensation target.
          </p>
        </div>
        <div className={styles.heroScore}>
          <div>
            <strong>{top ? `${top.match_score}%` : "—"}</strong>
            <span>Top current match</span>
          </div>
          <TrendingUp size={28} />
        </div>
      </section>

      <section className={styles.insights}>
        <article className={styles.insight}>
          <Target size={20} />
          <strong>{profile?.target_roles?.[0] ?? "Your selected direction"}</strong>
          <small>Recommendations are recalculated when you edit preferences.</small>
        </article>
        <article className={styles.insight}>
          <CircleDollarSign size={20} />
          <strong>{compensationMatches} visible roles meet your target</strong>
          <small>Published ranges below your minimum are deprioritized.</small>
        </article>
        <article className={styles.insight}>
          <FileText size={20} />
          <strong>Resume decisions persist with each application</strong>
          <small>Approved and rejected edits survive refresh and sign-in.</small>
        </article>
      </section>

      <section>
        <div className={styles.sectionHeader}>
          <div>
            <span className={styles.eyebrow}>Top opportunities</span>
            <h2>Jobs worth reviewing</h2>
          </div>
          <button className={styles.textButton} onClick={onViewAll}>
            View all matches <ArrowRight size={16} />
          </button>
        </div>
        {jobs.length ? (
          <div className={styles.jobsGrid}>
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                compared={compareIds.includes(job.id)}
                busy={busy === `save:${job.id}`}
                onOpen={() => onOpen(job.id)}
                onSave={() => onSave(job)}
                onCompare={() => onCompare(job.id)}
              />
            ))}
          </div>
        ) : (
          <div className={styles.empty}>
            <div>
              <h3>No ranked jobs match this search.</h3>
              <p>Clear the search box or update your candidate preferences.</p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function JobCard({
  job,
  compared,
  busy,
  onOpen,
  onSave,
  onCompare,
}: {
  job: Recommendation;
  compared: boolean;
  busy: boolean;
  onOpen: () => void;
  onSave: () => void;
  onCompare: () => void;
}) {
  return (
    <article className={styles.card}>
      <div className={styles.cardTop}>
        <div className={styles.companyRow}>
          <div className={styles.logo}>{initials(job.company_name)}</div>
          <div className={styles.companyCopy}>
            <strong>{job.company_name}</strong>
            <span>{job.source_label}</span>
          </div>
        </div>
        <button
          type="button"
          className={`${styles.iconButton} ${job.saved ? styles.iconButtonActive : ""}`}
          onClick={onSave}
          disabled={busy}
          aria-label={job.saved ? `Remove ${job.title} from saved jobs` : `Save ${job.title}`}
        >
          <Bookmark size={18} fill={job.saved ? "currentColor" : "none"} />
        </button>
      </div>
      <div>
        <h3>{job.title}</h3>
        <div className={styles.meta}>
          {job.location ? <span>{job.location}</span> : null}
          {job.work_mode ? <span>{job.work_mode}</span> : null}
          <span>{compensation(job)}</span>
        </div>
      </div>
      <div className={styles.matchSummary}>
        <div className={styles.matchScore}>{job.match_score}%</div>
        <p>{job.strengths[0]}</p>
      </div>
      <label className={styles.compareLabel}>
        <input type="checkbox" checked={compared} onChange={onCompare} /> Compare
      </label>
      <div className={styles.cardFooter}>
        <small>{relativePosting(job)}</small>
        <button className={`${styles.button} ${styles.primary}`} onClick={onOpen}>
          Review match
        </button>
      </div>
    </article>
  );
}

function MatchesView({
  jobs,
  selectedJob,
  compareIds,
  applicationByJob,
  busy,
  onSelect,
  onSave,
  onCompare,
  onTailor,
  onApplication,
}: {
  jobs: Recommendation[];
  selectedJob: Recommendation | null;
  compareIds: string[];
  applicationByJob: Map<string, ApplicationListItem>;
  busy: string | null;
  onSelect: (id: string) => void;
  onSave: (job: Recommendation) => void;
  onCompare: (id: string) => void;
  onTailor: () => void;
  onApplication: (id: string) => void;
}) {
  if (!selectedJob) return <div className={styles.empty}>No recommendation is selected.</div>;
  const application = applicationByJob.get(selectedJob.id);
  return (
    <div className={styles.matchesLayout}>
      <aside className={`${styles.panel} ${styles.matchList}`}>
        <span className={styles.eyebrow}>{jobs.length} ranked roles</span>
        <h2>Your best matches</h2>
        <p>Calculated from your persisted candidate profile and live database records.</p>
        <div className={styles.compactList}>
          {jobs.map((job) => (
            <button
              type="button"
              key={job.id}
              className={`${styles.compactJob} ${selectedJob.id === job.id ? styles.compactJobActive : ""}`}
              onClick={() => onSelect(job.id)}
            >
              <div className={styles.logoSmall}>{initials(job.company_name)}</div>
              <div className={styles.compactCopy}>
                <strong>{job.title}</strong>
                <span>{job.company_name} · {job.location ?? "Location flexible"}</span>
                <small>{compensation(job)}</small>
              </div>
              <div className={styles.compactScore}>{job.match_score}%</div>
            </button>
          ))}
        </div>
      </aside>

      <section className={`${styles.panel} ${styles.detailPanel}`}>
        <div className={styles.detailHeader}>
          <div className={styles.logoLarge}>{initials(selectedJob.company_name)}</div>
          <div className={styles.detailTitle}>
            <span>{selectedJob.company_name}</span>
            <h1>{selectedJob.title}</h1>
            <div className={styles.meta}>
              {selectedJob.location ? <span><MapPin size={13} /> {selectedJob.location}</span> : null}
              {selectedJob.work_mode ? <span>{selectedJob.work_mode}</span> : null}
              <span>{compensation(selectedJob)}</span>
            </div>
          </div>
          <button
            type="button"
            className={`${styles.iconButton} ${selectedJob.saved ? styles.iconButtonActive : ""}`}
            onClick={() => onSave(selectedJob)}
            disabled={busy === `save:${selectedJob.id}`}
            aria-label="Save selected job"
          >
            <Bookmark size={19} fill={selectedJob.saved ? "currentColor" : "none"} />
          </button>
        </div>

        <div className={styles.verifiedRow}>
          <ShieldCheck size={17} /> {selectedJob.source_label} · {relativePosting(selectedJob)}
        </div>

        <section className={styles.matchHero}>
          <div className={styles.largeScore}>{selectedJob.match_score}%</div>
          <div>
            <span className={styles.eyebrow}>Personalized match</span>
            <h2>This score comes from your saved profile.</h2>
            <p>{selectedJob.summary}</p>
          </div>
        </section>

        <div className={styles.analysisGrid}>
          <article className={styles.analysisGood}>
            <h3><Check size={17} /> Why you fit</h3>
            <ul>{selectedJob.strengths.map((strength) => <li key={strength}>{strength}</li>)}</ul>
          </article>
          <article className={styles.analysisGap}>
            <h3><Sparkles size={17} /> What to address</h3>
            <ul>{selectedJob.gaps.map((gap) => <li key={gap}>{gap}</li>)}</ul>
          </article>
        </div>

        <h3>Skills in the posting</h3>
        <div className={styles.skills}>
          {selectedJob.skills.length
            ? selectedJob.skills.map((skill) => <span key={skill}>{skill}</span>)
            : <span>Skills not listed</span>}
        </div>

        <label className={styles.compareLabel}>
          <input
            type="checkbox"
            checked={compareIds.includes(selectedJob.id)}
            onChange={() => onCompare(selectedJob.id)}
          /> Compare this job
        </label>

        <div className={styles.detailActions}>
          <button
            className={`${styles.button} ${styles.secondary}`}
            onClick={onTailor}
            disabled={busy === "tailoring"}
          >
            <FileText size={17} /> Tailor resume truthfully
          </button>
          <button
            className={`${styles.button} ${styles.primary}`}
            onClick={() => onApplication(selectedJob.id)}
            disabled={busy === `application:${selectedJob.id}`}
          >
            {application ? "Open application plan" : "Add to application plan"}
            <ArrowRight size={17} />
          </button>
        </div>
      </section>
    </div>
  );
}

function ResumeView({
  profile,
  tailoring,
  busy,
  onBack,
  onChange,
  onSave,
}: {
  profile: Profile | null;
  tailoring: TailoringResponse | null;
  busy: string | null;
  onBack: () => void;
  onChange: (edits: TailoringEdit[]) => void;
  onSave: (toTracker: boolean) => void;
}) {
  if (!tailoring) {
    return (
      <div className={styles.empty}>
        <div>
          <h3>Select a job before opening Resume Studio.</h3>
          <button className={`${styles.button} ${styles.secondary}`} onClick={onBack}>Back to matches</button>
        </div>
      </div>
    );
  }
  const approved = tailoring.edits.filter((edit) => edit.decision === "APPROVED").length;
  return (
    <div className={styles.stack}>
      <div className={styles.studioHeader}>
        <div>
          <button className={styles.textButton} onClick={onBack}><ArrowLeft size={16} /> Back to match</button>
          <span className={styles.eyebrow}>Resume studio</span>
          <h1>Tailor your resume without inventing anything.</h1>
          <p>
            Decisions are persisted to your application for {tailoring.job_title} at {tailoring.company_name}.
          </p>
        </div>
        <div className={styles.truthBadge}>
          <ShieldCheck size={18} /> Every claim traces to verified profile data
        </div>
      </div>

      <div className={styles.studioLayout}>
        <section className={styles.resumePaper}>
          <header>
            <h2>Alex Morgan</h2>
            <p>{profile?.headline ?? "Data Platform & Engineering Leader"}</p>
          </header>
          <div className={styles.resumeSection}>
            <h3>Executive summary</h3>
            <p>{profile?.summary}</p>
          </div>
          <div className={styles.resumeSection}>
            <h3>Selected experience</h3>
            {tailoring.edits.map((edit) => (
              <div
                key={edit.index}
                className={`${styles.resumeBullet} ${edit.decision === "APPROVED" ? styles.resumeBulletApproved : ""}`}
              >
                <span>•</span>
                <p>{edit.decision === "APPROVED" ? edit.text : edit.current}</p>
              </div>
            ))}
          </div>
        </section>

        <aside className={`${styles.panel} ${styles.editPanel}`}>
          <span className={styles.eyebrow}>{tailoring.edits.length} evidence-backed edits</span>
          <h2>Approve, reject, or revise each suggestion.</h2>
          <div className={styles.editList}>
            {tailoring.edits.map((edit) => (
              <article className={styles.editCard} key={edit.index}>
                <div className={styles.editTop}>
                  <span className={styles.editStatus}>
                    Edit {edit.index + 1} · {edit.decision.toLowerCase()}
                  </span>
                </div>
                <textarea
                  value={edit.text}
                  aria-label={`Resume edit ${edit.index + 1}`}
                  onChange={(event) =>
                    onChange(
                      tailoring.edits.map((item) =>
                        item.index === edit.index ? { ...item, text: event.target.value } : item,
                      ),
                    )
                  }
                />
                <div className={styles.evidence}><ShieldCheck size={14} /> {edit.evidence}</div>
                <div className={styles.decisionRow}>
                  <button
                    className={`${styles.button} ${styles.secondary}`}
                    onClick={() =>
                      onChange(
                        tailoring.edits.map((item) =>
                          item.index === edit.index ? { ...item, decision: "REJECTED" } : item,
                        ),
                      )
                    }
                  >
                    <X size={15} /> Reject
                  </button>
                  <button
                    className={`${styles.button} ${styles.primary}`}
                    onClick={() =>
                      onChange(
                        tailoring.edits.map((item) =>
                          item.index === edit.index ? { ...item, decision: "APPROVED" } : item,
                        ),
                      )
                    }
                  >
                    <Check size={15} /> Approve
                  </button>
                </div>
              </article>
            ))}
          </div>
          <div className={styles.detailActions}>
            <button
              className={`${styles.button} ${styles.secondary}`}
              onClick={() => onSave(false)}
              disabled={busy === "save-tailoring"}
            >
              Save decisions
            </button>
            <button
              className={`${styles.button} ${styles.primary}`}
              onClick={() => onSave(true)}
              disabled={busy === "save-tailoring" || approved === 0}
            >
              Use {approved} approved edit{approved === 1 ? "" : "s"} <ArrowRight size={16} />
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}

function TrackerView({
  applications,
  busy,
  onStatus,
  onOpenJob,
}: {
  applications: ApplicationListItem[];
  busy: string | null;
  onStatus: (application: ApplicationListItem, status: string) => void;
  onOpenJob: (jobId: string) => void;
}) {
  return (
    <div className={styles.stack}>
      <div className={styles.pageHeader}>
        <div>
          <span className={styles.eyebrow}>Application workspace</span>
          <h1>Move every application forward.</h1>
          <p>Status changes are written to PostgreSQL and preserved in the application event history.</p>
        </div>
      </div>
      <div className={styles.stats}>
        {statusColumns.map((column) => (
          <article className={styles.statCard} key={column.id}>
            <strong>{applications.filter((app) => applicationBucket(app.current_status) === column.id).length}</strong>
            <span>{column.label}</span>
          </article>
        ))}
      </div>
      <div className={styles.board}>
        {statusColumns.map((column) => {
          const items = applications.filter(
            (application) => applicationBucket(application.current_status) === column.id,
          );
          return (
            <section className={styles.column} key={column.id}>
              <div className={styles.columnHeader}>
                <h3>{column.label}</h3><span>{items.length}</span>
              </div>
              {items.length ? items.map((application) => {
                const currentIndex = statusProgression.indexOf(column.id);
                return (
                  <article className={styles.applicationCard} key={application.id}>
                    <div className={styles.companyRow}>
                      <div className={styles.logoSmall}>{initials(application.job.company_name)}</div>
                      <div className={styles.companyCopy}>
                        <strong>{application.job.title}</strong>
                        <span>{application.job.company_name}</span>
                      </div>
                    </div>
                    <small>{application.job.location ?? "Location not listed"}</small>
                    <div className={styles.applicationControls}>
                      <button className={styles.stageButton} onClick={() => onOpenJob(application.job_id)}>
                        Open job
                      </button>
                      {currentIndex > 0 ? (
                        <button
                          className={styles.stageButton}
                          disabled={busy === `status:${application.id}`}
                          onClick={() => onStatus(application, statusProgression[currentIndex - 1])}
                        >
                          ← Back
                        </button>
                      ) : null}
                      {currentIndex < statusProgression.length - 1 ? (
                        <button
                          className={styles.stageButton}
                          disabled={busy === `status:${application.id}`}
                          onClick={() => onStatus(application, statusProgression[currentIndex + 1])}
                        >
                          Move forward →
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              }) : <p>No applications in this stage.</p>}
            </section>
          );
        })}
      </div>
    </div>
  );
}

function PreferencesModal({
  profile,
  busy,
  onClose,
  onSave,
}: {
  profile: Profile;
  busy: boolean;
  onClose: () => void;
  onSave: (draft: PreferenceDraft) => void;
}) {
  const [draft, setDraft] = useState<PreferenceDraft>({
    targetRoles: profile.target_roles.join(", "),
    location: profile.location_text ?? "",
    minimumCompensation: String(profile.minimum_compensation ?? ""),
    remote: profile.work_modes.includes("REMOTE"),
    hybrid: profile.work_modes.includes("HYBRID"),
  });
  return (
    <div className={styles.modalBackdrop} role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="preferences-title">
        <div className={styles.modalHeader}>
          <div>
            <span className={styles.eyebrow}>Personalize recommendations</span>
            <h2 id="preferences-title">What should ApplyAI optimize for?</h2>
            <p>These values are saved to your candidate profile and used by the recommendation service.</p>
          </div>
          <button className={styles.iconButton} onClick={onClose} aria-label="Close preferences"><X size={18} /></button>
        </div>
        <div className={styles.modalBody}>
          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span>Target roles, separated by commas</span>
              <input value={draft.targetRoles} onChange={(event) => setDraft({ ...draft, targetRoles: event.target.value })} />
            </label>
            <label className={styles.field}>
              <span>Preferred location</span>
              <input value={draft.location} onChange={(event) => setDraft({ ...draft, location: event.target.value })} />
            </label>
            <label className={styles.field}>
              <span>Minimum compensation</span>
              <input type="number" value={draft.minimumCompensation} onChange={(event) => setDraft({ ...draft, minimumCompensation: event.target.value })} />
            </label>
            <div className={styles.field}>
              <span>Work modes</span>
              <label><input type="checkbox" checked={draft.remote} onChange={(event) => setDraft({ ...draft, remote: event.target.checked })} /> Remote</label>
              <label><input type="checkbox" checked={draft.hybrid} onChange={(event) => setDraft({ ...draft, hybrid: event.target.checked })} /> Hybrid</label>
            </div>
          </div>
        </div>
        <div className={styles.modalFooter}>
          <button className={`${styles.button} ${styles.secondary}`} onClick={onClose}>Cancel</button>
          <button className={`${styles.button} ${styles.primary}`} disabled={busy} onClick={() => onSave(draft)}>
            Save and re-rank jobs
          </button>
        </div>
      </section>
    </div>
  );
}

function CompareModal({
  jobs,
  onClose,
  onOpen,
}: {
  jobs: Recommendation[];
  onClose: () => void;
  onOpen: (id: string) => void;
}) {
  if (jobs.length !== 2) return null;
  const stronger = jobs[0].match_score >= jobs[1].match_score ? jobs[0] : jobs[1];
  const rows = [
    ["Match", `${jobs[0].match_score}%`, `${jobs[1].match_score}%`],
    ["Compensation", compensation(jobs[0]), compensation(jobs[1])],
    ["Location", `${jobs[0].location ?? "Not listed"} · ${jobs[0].work_mode ?? "Unknown"}`, `${jobs[1].location ?? "Not listed"} · ${jobs[1].work_mode ?? "Unknown"}`],
    ["Primary gap", jobs[0].gaps[0], jobs[1].gaps[0]],
    ["Posting", relativePosting(jobs[0]), relativePosting(jobs[1])],
  ];
  return (
    <div className={styles.modalBackdrop}>
      <section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="compare-title">
        <div className={styles.modalHeader}>
          <div><span className={styles.eyebrow}>Side-by-side decision</span><h2 id="compare-title">Which role deserves your time?</h2></div>
          <button className={styles.iconButton} onClick={onClose} aria-label="Close comparison"><X size={18} /></button>
        </div>
        <div className={styles.modalBody}>
          <div className={styles.compareGrid}>
            <div className={styles.compareLabel}>Criteria</div>
            <div><strong>{jobs[0].company_name}</strong></div>
            <div><strong>{jobs[1].company_name}</strong></div>
            {rows.map(([label, first, second]) => (
              <div key={label} style={{ display: "contents" }}>
                <div className={styles.compareLabel}>{label}</div><div>{first}</div><div>{second}</div>
              </div>
            ))}
          </div>
        </div>
        <div className={styles.modalFooter}>
          <button className={`${styles.button} ${styles.secondary}`} onClick={onClose}>Close</button>
          <button className={`${styles.button} ${styles.primary}`} onClick={() => onOpen(stronger.id)}>
            Open stronger match
          </button>
        </div>
      </section>
    </div>
  );
}
