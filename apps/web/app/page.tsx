import { UserButton } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { ArrowRight, CheckCircle2, LockKeyhole, Radar, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

function WorkspacePreview() {
  return (
    <div className="command-hero-visual" aria-label="Illustrative ApplyAI career workspace preview">
      <div className="command-orbit" aria-hidden="true" />
      <div className="command-floating-card one" aria-hidden="true">
        <strong>Recruiter Lens</strong>
        <span>4 supported · 1 partial · 1 gap to prepare for</span>
      </div>
      <div className="command-floating-card two" aria-hidden="true">
        <strong>Resume Share</strong>
        <span>Returning viewer · deep-read engagement signal</span>
      </div>
      <div className="command-preview">
        <div className="command-preview-bar">
          <div className="command-preview-brand"><i />ApplyAI</div>
          <span className="command-preview-chip">Illustrative workspace</span>
        </div>

        <div className="command-next-card">
          <small>Next best action</small>
          <strong>Review the opportunity that deserves your attention.</strong>
          <span>Your evidence is strong on the core role requirements. One skill gap is worth preparing before you apply.</span>
        </div>

        <div className="command-preview-grid">
          <div className="command-mini-card">
            <span className="command-mini-label">Opportunity intelligence</span>
            <span className="command-job-title">Senior Data Engineer</span>
            <span className="command-job-company">Example company · Remote</span>
            <div className="command-match-row">
              <span className="command-match-score">84</span>
              <div className="command-evidence-lines">
                <span className="command-evidence-line good"><i />Python, SQL, AWS evidenced</span>
                <span className="command-evidence-line gap"><i />Kafka ownership not evidenced</span>
              </div>
            </div>
          </div>

          <div className="command-mini-card">
            <span className="command-mini-label">Application pipeline</span>
            <div className="command-pipeline">
              <span><b>Acme</b> Interview prep</span>
              <span><b>Northstar</b> Follow-up due</span>
              <span><b>Vector</b> Resume viewed</span>
            </div>
          </div>

          <div className="command-mini-card">
            <span className="command-mini-label">Career evidence</span>
            <div className="command-evidence-lines">
              <span className="command-evidence-line good"><i />Verified experience</span>
              <span className="command-evidence-line good"><i />Target roles configured</span>
              <span className="command-evidence-line gap"><i />Portfolio can be strengthened</span>
            </div>
          </div>

          <div className="command-mini-card">
            <span className="command-mini-label">Engagement signal</span>
            <div className="command-signal">
              <span className="command-signal-ring" aria-hidden="true" />
              <div className="command-signal-copy">
                <strong>Deep read</strong>
                <span>Anonymous, privacy-safe engagement</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default async function Home() {
  const clerkConfigured = Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
      process.env.CLERK_SECRET_KEY,
  );
  const { userId } = clerkConfigured ? await auth() : { userId: null };

  const primaryHref = userId ? "/dashboard" : clerkConfigured ? "/sign-up" : "/demo";
  const primaryLabel = userId
    ? "Open my career workspace"
    : clerkConfigured
      ? "Build my career workspace"
      : "Explore the interactive demo";

  return (
    <main className="command-landing">
      <header className="site-header">
        <Link href="/" className="brand" aria-label="ApplyAI home">
          <span className="brand-mark">A</span>
          ApplyAI
        </Link>
        <nav aria-label="Account">
          {userId ? (
            <>
              <Link className="text-button" href="/dashboard">Open workspace</Link>
              <UserButton />
            </>
          ) : clerkConfigured ? (
            <>
              <Link className="text-button" href="/sign-in">Sign in</Link>
              <Link className="button" href="/sign-up">Create account</Link>
            </>
          ) : (
            <Link className="text-button" href="/demo">View product demo</Link>
          )}
        </nav>
      </header>

      <section className="command-hero">
        <div className="command-hero-copy">
          <div className="command-hero-kicker">Career Command OS</div>
          <h1>
            Your career, organized by <span>intelligence.</span>
          </h1>
          <p>
            ApplyAI turns your verified career evidence into a focused system for finding worthwhile roles,
            understanding fit, preparing stronger applications, tracking opportunities, and improving every next step.
          </p>
          <div className="command-hero-actions">
            <Link className="button" href={primaryHref}>
              {primaryLabel} <ArrowRight size={17} />
            </Link>
            <Link className="command-secondary-link" href={userId ? "/jobs" : "/demo"}>
              <Radar size={17} /> See how Recruiter Lens works
            </Link>
          </div>
          <div className="command-trust-row" aria-label="ApplyAI product principles">
            <span><i className="command-trust-dot" />Private by default</span>
            <span><ShieldCheck size={13} />Evidence before AI claims</span>
            <span><LockKeyhole size={13} />No hiring-probability guesses</span>
          </div>
        </div>
        <WorkspacePreview />
      </section>

      <section id="foundation" className="command-foundation" aria-label="ApplyAI workflow">
        <div className="command-foundation-heading">
          <h2>One calm system for the entire job-search lifecycle.</h2>
          <p>
            Stop rebuilding context across job boards, spreadsheets, documents, and AI chats. ApplyAI keeps the evidence,
            opportunity, preparation, follow-up, and learning loop connected.
          </p>
        </div>
        <div className="command-value-grid">
          <article className="command-value-card">
            <span className="step">01 · EVIDENCE</span>
            <h3>Start from what you can defend.</h3>
            <p>
              Upload a résumé, review the parser draft, and build a candidate-owned Career Memory. Nothing extracted becomes
              truth until you confirm it.
            </p>
          </article>
          <article className="command-value-card">
            <span className="step">02 · DECISION</span>
            <h3>Know which jobs deserve your energy.</h3>
            <p>
              See strong evidence, partial evidence, missing evidence, freshness, provenance, and Recruiter Lens concerns before
              deciding whether to pursue a role.
            </p>
          </article>
          <article className="command-value-card">
            <span className="step">03 · MOMENTUM</span>
            <h3>Turn opportunities into an operating rhythm.</h3>
            <p>
              Keep résumé variants, outreach, interview prep, follow-ups, Resume Share engagement, and application status in one
              candidate command center.
            </p>
          </article>
        </div>
        <div className="command-trust-row" style={{ marginTop: 24 }}>
          <span><CheckCircle2 size={13} />Human-reviewed evidence</span>
          <span><Sparkles size={13} />AI as preparation, not truth</span>
          <span><ShieldCheck size={13} />Candidate-controlled privacy</span>
        </div>
      </section>
    </main>
  );
}
