"use client";

import {
  ArrowRight,
  Bookmark,
  BriefcaseBusiness,
  Check,
  ChevronLeft,
  CircleDollarSign,
  FileCheck2,
  FileText,
  Home,
  MapPin,
  Menu,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import styles from "./demo.module.css";

type View = "today" | "matches" | "resume" | "tracker";

type DemoJob = {
  id: string;
  company: string;
  initials: string;
  title: string;
  location: string;
  workMode: string;
  salary: string;
  match: number;
  posted: string;
  source: string;
  summary: string;
  strengths: string[];
  gaps: string[];
  skills: string[];
};

const jobs: DemoJob[] = [
  {
    id: "northstar",
    company: "Northstar AI",
    initials: "NA",
    title: "Senior Manager, Data Platform",
    location: "Boston, MA",
    workMode: "Hybrid",
    salary: "$245K–$310K",
    match: 94,
    posted: "Posted 6 hours ago",
    source: "Verified company posting",
    summary:
      "Lead the data platform organization supporting model training, evaluation, and customer analytics across a fast-growing AI product suite.",
    strengths: [
      "You have 9+ years leading production data platforms.",
      "Your AWS, Snowflake, and distributed systems experience matches the core stack.",
      "Your recent work shows cross-functional leadership with product and ML teams.",
    ],
    gaps: [
      "The role asks for direct ownership of a 20+ person organization; your resume currently shows 12.",
      "The posting emphasizes model-evaluation pipelines, which are not explicit in your current resume.",
    ],
    skills: ["AWS", "Snowflake", "Python", "Data Architecture", "People Leadership"],
  },
  {
    id: "vertex",
    company: "Vertex Labs",
    initials: "VL",
    title: "Director, AI Data Infrastructure",
    location: "New York, NY",
    workMode: "Remote-friendly",
    salary: "$270K–$345K",
    match: 89,
    posted: "Posted yesterday",
    source: "Verified ATS posting",
    summary:
      "Own the roadmap for enterprise data infrastructure used by research, safety, and applied AI engineering teams.",
    strengths: [
      "Your platform architecture background aligns closely with the role mandate.",
      "Your experience modernizing legacy data systems maps to the first-year goals.",
      "Your stakeholder leadership is stronger than most requirements in the posting.",
    ],
    gaps: [
      "The role prefers prior work in a research-heavy AI organization.",
      "Your resume needs a clearer example of operating at director-level budget scope.",
    ],
    skills: ["Platform Strategy", "Data Governance", "Kubernetes", "ML Infrastructure"],
  },
  {
    id: "harbor",
    company: "Harbor Health",
    initials: "HH",
    title: "Head of Data Engineering",
    location: "Cambridge, MA",
    workMode: "Hybrid",
    salary: "$225K–$285K",
    match: 84,
    posted: "Posted 2 days ago",
    source: "Verified company posting",
    summary:
      "Build a modern healthcare data platform and grow the engineering team responsible for analytics, interoperability, and AI readiness.",
    strengths: [
      "Your regulated-data experience is highly relevant.",
      "Your record of building teams from the ground up matches the company stage.",
      "Your architecture and delivery background covers nearly every technical requirement.",
    ],
    gaps: [
      "FHIR and healthcare interoperability are preferred but not shown on your resume.",
      "The compensation ceiling is below your stated target.",
    ],
    skills: ["Healthcare Data", "Data Platforms", "Team Building", "Governance"],
  },
];

const navigation: Array<{ id: View; label: string; icon: typeof Home }> = [
  { id: "today", label: "Today", icon: Home },
  { id: "matches", label: "Best matches", icon: Target },
  { id: "resume", label: "Resume studio", icon: FileText },
  { id: "tracker", label: "Applications", icon: BriefcaseBusiness },
];

export function CandidateValueDemo() {
  const [view, setView] = useState<View>("today");
  const [selectedJobId, setSelectedJobId] = useState(jobs[0].id);
  const [savedJobIds, setSavedJobIds] = useState<Set<string>>(
    () => new Set([jobs[1].id]),
  );
  const [appliedJobIds, setAppliedJobIds] = useState<Set<string>>(() => new Set());
  const [approvedEdits, setApprovedEdits] = useState<Set<number>>(() => new Set([0]));
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0],
    [selectedJobId],
  );

  const navigate = (nextView: View) => {
    setView(nextView);
    setMobileMenuOpen(false);
  };

  const openJob = (jobId: string) => {
    setSelectedJobId(jobId);
    setView("matches");
    setMobileMenuOpen(false);
  };

  const toggleSaved = (jobId: string) => {
    setSavedJobIds((current) => {
      const next = new Set(current);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
      }
      return next;
    });
  };

  const markApplied = (jobId: string) => {
    setAppliedJobIds((current) => new Set(current).add(jobId));
    setView("tracker");
  };

  return (
    <main className={styles.demoShell}>
      <aside className={`${styles.sidebar} ${mobileMenuOpen ? styles.sidebarOpen : ""}`}>
        <div className={styles.brandRow}>
          <span className={styles.brandMark}>A</span>
          <span>ApplyAI</span>
          <button
            type="button"
            className={styles.mobileClose}
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>

        <div className={styles.profileCard}>
          <div className={styles.avatar}>AM</div>
          <div>
            <strong>Alex Morgan</strong>
            <span>Data platform leader</span>
          </div>
        </div>

        <nav className={styles.nav} aria-label="Demo navigation">
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
              </button>
            );
          })}
        </nav>

        <div className={styles.sidebarGoal}>
          <span>Search goal</span>
          <strong>AI data leadership</strong>
          <small>Boston or remote · $250K+</small>
        </div>
      </aside>

      {mobileMenuOpen ? (
        <button
          type="button"
          className={styles.mobileOverlay}
          onClick={() => setMobileMenuOpen(false)}
          aria-label="Close navigation"
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
          <div className={styles.searchBar}>
            <Search size={18} />
            <span>Search roles, companies, or skills</span>
            <kbd>⌘ K</kbd>
          </div>
          <div className={styles.demoBadge}>
            <Sparkles size={15} />
            Interactive product demo
          </div>
        </header>

        <div className={styles.pageBody}>
          {view === "today" ? (
            <TodayView
              savedJobIds={savedJobIds}
              onOpenJob={openJob}
              onToggleSaved={toggleSaved}
              onViewAll={() => navigate("matches")}
            />
          ) : null}

          {view === "matches" ? (
            <MatchesView
              selectedJob={selectedJob}
              savedJobIds={savedJobIds}
              appliedJobIds={appliedJobIds}
              onSelectJob={setSelectedJobId}
              onToggleSaved={toggleSaved}
              onTailor={() => navigate("resume")}
              onMarkApplied={markApplied}
            />
          ) : null}

          {view === "resume" ? (
            <ResumeStudio
              selectedJob={selectedJob}
              approvedEdits={approvedEdits}
              onToggleEdit={(index) => {
                setApprovedEdits((current) => {
                  const next = new Set(current);
                  if (next.has(index)) {
                    next.delete(index);
                  } else {
                    next.add(index);
                  }
                  return next;
                });
              }}
              onReviewApplication={() => navigate("matches")}
            />
          ) : null}

          {view === "tracker" ? (
            <TrackerView
              appliedJobIds={appliedJobIds}
              savedJobIds={savedJobIds}
              onOpenJob={openJob}
            />
          ) : null}
        </div>
      </section>
    </main>
  );
}

function TodayView({
  savedJobIds,
  onOpenJob,
  onToggleSaved,
  onViewAll,
}: {
  savedJobIds: Set<string>;
  onOpenJob: (jobId: string) => void;
  onToggleSaved: (jobId: string) => void;
  onViewAll: () => void;
}) {
  return (
    <div className={styles.contentStack}>
      <section className={styles.heroPanel}>
        <div>
          <span className={styles.eyebrow}>Your job search, prioritized</span>
          <h1>Good evening, Alex.</h1>
          <p>
            We reviewed 186 new roles today. These 3 are genuinely worth your time.
          </p>
        </div>
        <div className={styles.heroScore}>
          <div>
            <strong>94%</strong>
            <span>Top match today</span>
          </div>
          <TrendingUp size={28} />
        </div>
      </section>

      <section className={styles.insightGrid}>
        <article className={styles.insightCard}>
          <Target size={20} />
          <div>
            <span>Best-fit direction</span>
            <strong>AI data platform leadership</strong>
            <small>Your experience is strongest for senior manager and director roles.</small>
          </div>
        </article>
        <article className={styles.insightCard}>
          <CircleDollarSign size={20} />
          <div>
            <span>Compensation fit</span>
            <strong>2 roles meet your $250K target</strong>
            <small>One strong role falls below your preferred range.</small>
          </div>
        </article>
        <article className={styles.insightCard}>
          <FileCheck2 size={20} />
          <div>
            <span>Resume opportunity</span>
            <strong>Make AI platform impact more visible</strong>
            <small>Three truthful edits could improve relevance for your top match.</small>
          </div>
        </article>
      </section>

      <section>
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.eyebrow}>Top opportunities</span>
            <h2>Jobs worth pursuing</h2>
          </div>
          <button type="button" className={styles.textButton} onClick={onViewAll}>
            View all matches <ArrowRight size={16} />
          </button>
        </div>
        <div className={styles.jobGrid}>
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              saved={savedJobIds.has(job.id)}
              onOpen={() => onOpenJob(job.id)}
              onToggleSaved={() => onToggleSaved(job.id)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

function JobCard({
  job,
  saved,
  onOpen,
  onToggleSaved,
}: {
  job: DemoJob;
  saved: boolean;
  onOpen: () => void;
  onToggleSaved: () => void;
}) {
  return (
    <article className={styles.jobCard}>
      <div className={styles.jobCardTop}>
        <div className={styles.companyLogo}>{job.initials}</div>
        <button
          type="button"
          className={`${styles.iconButton} ${saved ? styles.iconButtonSaved : ""}`}
          onClick={onToggleSaved}
          aria-label={saved ? `Remove ${job.title} from saved jobs` : `Save ${job.title}`}
        >
          <Bookmark size={18} fill={saved ? "currentColor" : "none"} />
        </button>
      </div>
      <div>
        <span className={styles.companyName}>{job.company}</span>
        <h3>{job.title}</h3>
        <div className={styles.jobMeta}>
          <span><MapPin size={14} /> {job.location}</span>
          <span>{job.workMode}</span>
          <span>{job.salary}</span>
        </div>
      </div>
      <div className={styles.matchSummary}>
        <div className={styles.matchRing} style={{ "--score": `${job.match * 3.6}deg` } as React.CSSProperties}>
          <span>{job.match}%</span>
        </div>
        <p>{job.strengths[0]}</p>
      </div>
      <div className={styles.jobCardFooter}>
        <span>{job.posted}</span>
        <button type="button" className={styles.primaryButtonSmall} onClick={onOpen}>
          Review match
        </button>
      </div>
    </article>
  );
}

function MatchesView({
  selectedJob,
  savedJobIds,
  appliedJobIds,
  onSelectJob,
  onToggleSaved,
  onTailor,
  onMarkApplied,
}: {
  selectedJob: DemoJob;
  savedJobIds: Set<string>;
  appliedJobIds: Set<string>;
  onSelectJob: (jobId: string) => void;
  onToggleSaved: (jobId: string) => void;
  onTailor: () => void;
  onMarkApplied: (jobId: string) => void;
}) {
  return (
    <div className={styles.matchesLayout}>
      <section className={styles.matchListPanel}>
        <div className={styles.panelHeading}>
          <span className={styles.eyebrow}>186 roles reviewed</span>
          <h1>Your best matches</h1>
          <p>Ranked by career fit, preferences, compensation, and posting quality.</p>
        </div>
        <div className={styles.compactJobList}>
          {jobs.map((job) => (
            <button
              type="button"
              key={job.id}
              className={`${styles.compactJob} ${selectedJob.id === job.id ? styles.compactJobActive : ""}`}
              onClick={() => onSelectJob(job.id)}
            >
              <div className={styles.companyLogoSmall}>{job.initials}</div>
              <div className={styles.compactJobCopy}>
                <strong>{job.title}</strong>
                <span>{job.company} · {job.location}</span>
                <small>{job.salary}</small>
              </div>
              <div className={styles.compactScore}>{job.match}%</div>
            </button>
          ))}
        </div>
      </section>

      <section className={styles.jobDetailPanel}>
        <div className={styles.detailHeader}>
          <button type="button" className={styles.mobileBack} aria-label="Back to job list">
            <ChevronLeft size={18} />
          </button>
          <div className={styles.companyLogoLarge}>{selectedJob.initials}</div>
          <div className={styles.detailTitle}>
            <span>{selectedJob.company}</span>
            <h2>{selectedJob.title}</h2>
            <div className={styles.detailMeta}>
              <span><MapPin size={15} /> {selectedJob.location}</span>
              <span>{selectedJob.workMode}</span>
              <span>{selectedJob.salary}</span>
            </div>
          </div>
          <button
            type="button"
            className={`${styles.iconButton} ${savedJobIds.has(selectedJob.id) ? styles.iconButtonSaved : ""}`}
            onClick={() => onToggleSaved(selectedJob.id)}
            aria-label="Save job"
          >
            <Bookmark
              size={19}
              fill={savedJobIds.has(selectedJob.id) ? "currentColor" : "none"}
            />
          </button>
        </div>

        <div className={styles.verifiedRow}>
          <ShieldCheck size={17} />
          <span>{selectedJob.source}</span>
          <span>·</span>
          <span>{selectedJob.posted}</span>
        </div>

        <section className={styles.matchHero}>
          <div className={styles.largeMatchScore}>{selectedJob.match}%</div>
          <div>
            <span className={styles.eyebrow}>Strong match</span>
            <h3>This role aligns closely with your next move.</h3>
            <p>{selectedJob.summary}</p>
          </div>
        </section>

        <div className={styles.analysisGrid}>
          <article className={styles.analysisCardPositive}>
            <div className={styles.analysisCardHeader}>
              <Check size={19} />
              <h3>Why you fit</h3>
            </div>
            <ul>
              {selectedJob.strengths.map((strength) => (
                <li key={strength}>{strength}</li>
              ))}
            </ul>
          </article>
          <article className={styles.analysisCardNeutral}>
            <div className={styles.analysisCardHeader}>
              <Sparkles size={19} />
              <h3>What to address</h3>
            </div>
            <ul>
              {selectedJob.gaps.map((gap) => (
                <li key={gap}>{gap}</li>
              ))}
            </ul>
          </article>
        </div>

        <section className={styles.skillsSection}>
          <h3>Skills alignment</h3>
          <div className={styles.skillRow}>
            {selectedJob.skills.map((skill) => (
              <span key={skill}>{skill}</span>
            ))}
          </div>
        </section>

        <div className={styles.detailActions}>
          <button type="button" className={styles.secondaryButton} onClick={onTailor}>
            <FileText size={17} />
            Tailor resume truthfully
          </button>
          <button
            type="button"
            className={styles.primaryButton}
            onClick={() => onMarkApplied(selectedJob.id)}
            disabled={appliedJobIds.has(selectedJob.id)}
          >
            {appliedJobIds.has(selectedJob.id) ? "Application tracked" : "Add to application plan"}
            <ArrowRight size={17} />
          </button>
        </div>
      </section>
    </div>
  );
}

function ResumeStudio({
  selectedJob,
  approvedEdits,
  onToggleEdit,
  onReviewApplication,
}: {
  selectedJob: DemoJob;
  approvedEdits: Set<number>;
  onToggleEdit: (index: number) => void;
  onReviewApplication: () => void;
}) {
  const edits = [
    {
      current: "Led the modernization of enterprise data systems across multiple business units.",
      suggested:
        "Led the modernization of enterprise data platforms across four business units, improving pipeline reliability and reducing delivery time by 35%.",
      evidence: "Supported by your uploaded resume: scope, four business units, and 35% improvement.",
    },
    {
      current: "Partnered with engineering and analytics stakeholders on platform strategy.",
      suggested:
        "Partnered with product, ML, analytics, and security leaders to define a three-year data platform roadmap supporting AI-enabled products.",
      evidence: "Supported by your resume and confirmed career profile. No new claim added.",
    },
    {
      current: "Managed a team of data engineers.",
      suggested:
        "Built and led a 12-person data engineering organization spanning platform, ingestion, governance, and developer enablement.",
      evidence: "Supported by your verified team-size and responsibility details.",
    },
  ];

  return (
    <div className={styles.contentStack}>
      <section className={styles.studioHeader}>
        <div>
          <span className={styles.eyebrow}>Resume studio</span>
          <h1>Tailor your resume without inventing anything.</h1>
          <p>
            These edits make your verified experience clearer for {selectedJob.title} at {selectedJob.company}.
          </p>
        </div>
        <div className={styles.truthBadge}>
          <ShieldCheck size={18} />
          Every claim must trace to your profile
        </div>
      </section>

      <div className={styles.studioLayout}>
        <section className={styles.resumePreview}>
          <div className={styles.resumePaper}>
            <div className={styles.resumeNameRow}>
              <div>
                <h2>Alex Morgan</h2>
                <p>Data Platform & Engineering Leader</p>
              </div>
              <span>Boston, MA · alex@example.com</span>
            </div>
            <div className={styles.resumeSection}>
              <h3>Executive summary</h3>
              <p>
                Data platform leader with 12 years of experience building reliable data products,
                scaling engineering teams, and modernizing cloud infrastructure for regulated and
                high-growth organizations.
              </p>
            </div>
            <div className={styles.resumeSection}>
              <h3>Selected experience</h3>
              {edits.map((edit, index) => (
                <div
                  key={edit.current}
                  className={`${styles.resumeBullet} ${approvedEdits.has(index) ? styles.resumeBulletApproved : ""}`}
                >
                  <span>•</span>
                  <p>{approvedEdits.has(index) ? edit.suggested : edit.current}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <aside className={styles.editPanel}>
          <div className={styles.panelHeadingCompact}>
            <span className={styles.eyebrow}>3 recommended edits</span>
            <h2>Make the strongest evidence easier to see.</h2>
          </div>
          <div className={styles.editList}>
            {edits.map((edit, index) => (
              <article key={edit.current} className={styles.editCard}>
                <div className={styles.editCardTop}>
                  <span>Edit {index + 1}</span>
                  <button
                    type="button"
                    className={approvedEdits.has(index) ? styles.approvedButton : styles.approveButton}
                    onClick={() => onToggleEdit(index)}
                  >
                    {approvedEdits.has(index) ? <Check size={15} /> : null}
                    {approvedEdits.has(index) ? "Approved" : "Approve"}
                  </button>
                </div>
                <p className={styles.suggestedCopy}>{edit.suggested}</p>
                <div className={styles.evidenceNote}>
                  <ShieldCheck size={15} />
                  {edit.evidence}
                </div>
              </article>
            ))}
          </div>
          <button type="button" className={styles.primaryButtonWide} onClick={onReviewApplication}>
            Use {approvedEdits.size} approved edits
            <ArrowRight size={17} />
          </button>
        </aside>
      </div>
    </div>
  );
}

function TrackerView({
  appliedJobIds,
  savedJobIds,
  onOpenJob,
}: {
  appliedJobIds: Set<string>;
  savedJobIds: Set<string>;
  onOpenJob: (jobId: string) => void;
}) {
  const savedJobs = jobs.filter((job) => savedJobIds.has(job.id));
  const appliedJobs = jobs.filter((job) => appliedJobIds.has(job.id));

  return (
    <div className={styles.contentStack}>
      <section className={styles.studioHeader}>
        <div>
          <span className={styles.eyebrow}>Application workspace</span>
          <h1>Know exactly what needs your attention.</h1>
          <p>Keep decisions, deadlines, materials, and follow-ups in one calm workspace.</p>
        </div>
      </section>

      <div className={styles.trackerSummary}>
        <article><strong>{savedJobs.length}</strong><span>Saved to review</span></article>
        <article><strong>{appliedJobs.length}</strong><span>In application plan</span></article>
        <article><strong>1</strong><span>Follow-up this week</span></article>
        <article><strong>0</strong><span>Overdue tasks</span></article>
      </div>

      <section className={styles.trackerBoard}>
        <TrackerColumn title="Saved" count={savedJobs.length}>
          {savedJobs.length ? savedJobs.map((job) => (
            <TrackerCard key={job.id} job={job} label="Review match" onOpen={() => onOpenJob(job.id)} />
          )) : <EmptyTrackerCopy>Save a strong match to keep it here.</EmptyTrackerCopy>}
        </TrackerColumn>
        <TrackerColumn title="Preparing" count={appliedJobs.length}>
          {appliedJobs.length ? appliedJobs.map((job) => (
            <TrackerCard key={job.id} job={job} label="Complete application" onOpen={() => onOpenJob(job.id)} />
          )) : <EmptyTrackerCopy>Add a job to your application plan.</EmptyTrackerCopy>}
        </TrackerColumn>
        <TrackerColumn title="Applied" count={1}>
          <article className={styles.trackerCard}>
            <div className={styles.companyLogoSmall}>OC</div>
            <div>
              <strong>Director of Data Engineering</strong>
              <span>Orion Cloud</span>
              <small>Applied Jul 30 · Follow up Aug 6</small>
            </div>
          </article>
        </TrackerColumn>
        <TrackerColumn title="Interviewing" count={1}>
          <article className={styles.trackerCardHighlight}>
            <div className={styles.companyLogoSmall}>LM</div>
            <div>
              <strong>Head of Data Platform</strong>
              <span>Lumen Markets</span>
              <small>Hiring manager interview · Tuesday, 2:00 PM</small>
            </div>
          </article>
        </TrackerColumn>
      </section>
    </div>
  );
}

function TrackerColumn({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className={styles.trackerColumn}>
      <div className={styles.trackerColumnHeader}>
        <h2>{title}</h2>
        <span>{count}</span>
      </div>
      <div className={styles.trackerColumnBody}>{children}</div>
    </section>
  );
}

function TrackerCard({
  job,
  label,
  onOpen,
}: {
  job: DemoJob;
  label: string;
  onOpen: () => void;
}) {
  return (
    <button type="button" className={styles.trackerCardButton} onClick={onOpen}>
      <div className={styles.companyLogoSmall}>{job.initials}</div>
      <div>
        <strong>{job.title}</strong>
        <span>{job.company}</span>
        <small>{label}</small>
      </div>
    </button>
  );
}

function EmptyTrackerCopy({ children }: { children: React.ReactNode }) {
  return <p className={styles.emptyTracker}>{children}</p>;
}
