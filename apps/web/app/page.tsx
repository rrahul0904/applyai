import { SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import Link from "next/link";

export default async function Home() {
  const clerkConfigured = Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
      process.env.CLERK_SECRET_KEY,
  );
  const { userId } = clerkConfigured ? await auth() : { userId: null };

  return (
    <main>
      <header className="site-header">
        <Link href="/" className="brand" aria-label="ApplyAI home">
          <span className="brand-mark">A</span>
          ApplyAI
        </Link>
        <nav aria-label="Account">
          {userId ? (
            <>
              <Link className="text-button" href="/dashboard">
                Open workspace
              </Link>
              <UserButton />
            </>
          ) : clerkConfigured ? (
            <>
              <SignInButton>
                <button className="text-button">Sign in</button>
              </SignInButton>
              <SignUpButton>
                <button className="button button-small">Create account</button>
              </SignUpButton>
            </>
          ) : (
            <Link className="text-button" href="/demo">
              View product demo
            </Link>
          )}
        </nav>
      </header>

      <section className="hero">
        <div className="eyebrow">Fewer applications. Better opportunities.</div>
        <h1>Know which jobs are truly worth your time.</h1>
        <p>
          ApplyAI ranks opportunities for your goals, explains why you fit, helps
          you strengthen a truthful application, and keeps every next step clear.
        </p>
        <div className="hero-actions">
          {userId ? (
            <Link className="button" href="/dashboard">
              Continue to your workspace
            </Link>
          ) : (
            <Link className="button" href="/demo">
              Try the interactive demo
            </Link>
          )}
          {!userId && clerkConfigured ? (
            <SignUpButton>
              <button className="text-button">Create your workspace</button>
            </SignUpButton>
          ) : null}
          <a className="text-link" href="#foundation">
            See how it helps <span aria-hidden="true">↓</span>
          </a>
        </div>
      </section>

      <section id="foundation" className="value-grid" aria-label="ApplyAI workflow">
        <article>
          <span className="step">01</span>
          <h2>Start with your real experience</h2>
          <p>
            Turn your resume and preferences into an editable career profile that
            reflects where you have been and where you want to go next.
          </p>
        </article>
        <article>
          <span className="step">02</span>
          <h2>See why each job fits</h2>
          <p>
            Focus on a small set of strong opportunities with clear strengths,
            realistic gaps, salary fit, freshness, and source confidence.
          </p>
        </article>
        <article>
          <span className="step">03</span>
          <h2>Apply with more confidence</h2>
          <p>
            Approve truthful resume improvements, prepare the application, and keep
            deadlines, follow-ups, and interviews in one calm workspace.
          </p>
        </article>
      </section>
    </main>
  );
}
