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
            <span className="configuration-label">Authentication setup required</span>
          )}
        </nav>
      </header>

      <section className="hero">
        <div className="eyebrow">Fewer applications. Better decisions.</div>
        <h1>Know which jobs are worth your time.</h1>
        <p>
          ApplyAI brings your career profile, job search, application materials,
          and follow-ups into one private workspace.
        </p>
        <div className="hero-actions">
          {userId ? (
            <Link className="button" href="/dashboard">
              Continue to your workspace
            </Link>
          ) : clerkConfigured ? (
            <SignUpButton>
              <button className="button">Start your job search</button>
            </SignUpButton>
          ) : (
            <button className="button" disabled>
              Configure Clerk to continue
            </button>
          )}
          <a className="text-link" href="#foundation">
            See how it works <span aria-hidden="true">↓</span>
          </a>
        </div>
      </section>

      <section id="foundation" className="value-grid" aria-label="ApplyAI workflow">
        <article>
          <span className="step">01</span>
          <h2>Build one verified profile</h2>
          <p>
            Keep document facts separate from your own corrections and future AI
            suggestions.
          </p>
        </article>
        <article>
          <span className="step">02</span>
          <h2>Find relevant, current jobs</h2>
          <p>
            Search canonical job records with clear source, salary, and freshness
            information.
          </p>
        </article>
        <article>
          <span className="step">03</span>
          <h2>Track every decision</h2>
          <p>
            Save jobs, prepare applications, and preserve every status change in
            an immutable history.
          </p>
        </article>
      </section>
    </main>
  );
}
