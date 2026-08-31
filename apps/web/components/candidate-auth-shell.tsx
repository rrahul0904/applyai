import Link from "next/link";
import { ArrowRight, BriefcaseBusiness, CheckCircle2, LockKeyhole, ScanSearch } from "lucide-react";
import styles from "./candidate-auth-shell.module.css";

type CandidateAuthShellProps = {
  children: React.ReactNode;
  mode: "sign-in" | "sign-up";
};

const proofPoints = [
  {
    icon: ScanSearch,
    title: "See the recruiter view before you apply",
    detail: "Recruiter Lens shows supported evidence, partial matches, and the gaps likely to create questions.",
  },
  {
    icon: BriefcaseBusiness,
    title: "Keep each opportunity in one workspace",
    detail: "Resume tailoring, application prep, outreach, interview practice, and follow-up stay connected to the role.",
  },
  {
    icon: LockKeyhole,
    title: "Stay in control of your career data",
    detail: "Your resume stays private by default, generated claims stay evidence-bound, and external actions require your approval.",
  },
];

export function CandidateAuthShell({ children, mode }: CandidateAuthShellProps) {
  const isSignUp = mode === "sign-up";

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.brand} aria-label="ApplyAI home">
          <span className={styles.brandMark}>A</span>
          <span>ApplyAI</span>
        </Link>
        <div className={styles.headerAction}>
          <span>{isSignUp ? "Already have a workspace?" : "New to ApplyAI?"}</span>
          <Link href={isSignUp ? "/sign-in" : "/sign-up"}>
            {isSignUp ? "Sign in" : "Create account"}
          </Link>
        </div>
      </header>

      <section className={styles.layout}>
        <div className={styles.story}>
          <div className={styles.kicker}>Your candidate command center</div>
          <h1>{isSignUp ? "Make every application more intentional." : "Welcome back to your job search."}</h1>
          <p className={styles.lead}>
            ApplyAI remembers your verified career evidence, helps you focus on stronger roles,
            and carries the context from discovery through application, interview, and follow-up.
          </p>

          <div className={styles.journey} aria-label="ApplyAI candidate workflow">
            <div className={styles.journeyHeader}>
              <span>One connected workflow</span>
              <span className={styles.journeyStatus}>Candidate controlled</span>
            </div>
            <div className={styles.journeySteps}>
              {[
                "Find a role",
                "Check recruiter fit",
                "Strengthen evidence",
                "Prepare the application",
                "Practice the interview",
              ].map((step, index) => (
                <div className={styles.journeyStep} key={step}>
                  <span className={styles.stepNumber}>{String(index + 1).padStart(2, "0")}</span>
                  <span>{step}</span>
                  {index < 4 ? <ArrowRight size={15} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
                </div>
              ))}
            </div>
          </div>

          <div className={styles.proofGrid}>
            {proofPoints.map(({ icon: Icon, title, detail }) => (
              <article className={styles.proofCard} key={title}>
                <span className={styles.proofIcon}><Icon size={18} aria-hidden="true" /></span>
                <div>
                  <h2>{title}</h2>
                  <p>{detail}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className={styles.authPanel} aria-label={isSignUp ? "Create your ApplyAI account" : "Sign in to ApplyAI"}>
          <div className={styles.authIntro}>
            <span className={styles.authEyebrow}>{isSignUp ? "Create your workspace" : "Candidate sign in"}</span>
            <h2>{isSignUp ? "Start with your real experience." : "Continue where you left off."}</h2>
            <p>
              {isSignUp
                ? "Create an account, add your resume, and build a career profile you can reuse across every opportunity."
                : "Your saved jobs, application workspaces, resume versions, and interview preparation are waiting."}
            </p>
          </div>
          <div className={styles.clerkSlot}>{children}</div>
          <div className={styles.trustRow}>
            <span><LockKeyhole size={14} aria-hidden="true" /> Private by default</span>
            <span><CheckCircle2 size={14} aria-hidden="true" /> Evidence-bound AI</span>
          </div>
        </aside>
      </section>

      <footer className={styles.footer}>
        <span>ApplyAI is a candidate preparation tool. Readiness signals are not hiring probabilities.</span>
        <div>
          <Link href="/settings">Privacy</Link>
          <Link href="/">Home</Link>
        </div>
      </footer>
    </main>
  );
}
