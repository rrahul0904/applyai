import { redirect } from "next/navigation";
import Link from "next/link";
import { devAuthEnabled, getApplyAISession } from "@/lib/auth/session";
import { devSignIn } from "./actions";

export default async function DevLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  if (!devAuthEnabled()) redirect("/");
  const session = await getApplyAISession();
  if (session.authenticated) redirect("/dashboard");
  const { error } = await searchParams;

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="dev-login-title">
        <Link className="brand" href="/">
          <span className="brand-mark">A</span>
          ApplyAI
        </Link>
        <p className="eyebrow">Development sign-in</p>
        <h1 id="dev-login-title">Continue as a test candidate</h1>
        <p>
          This controlled identity uses the real PostgreSQL user and authorization
          paths. It cannot run in production.
        </p>
        <form action={devSignIn} className="form-stack">
          <label htmlFor="email">Test candidate email</label>
          <input
            id="email"
            name="email"
            type="email"
            defaultValue="alex.candidate@example.test"
            required
            aria-describedby={error ? "email-error" : undefined}
          />
          {error ? (
            <p id="email-error" className="field-error" role="alert">
              Enter a valid email address.
            </p>
          ) : null}
          <button className="button" type="submit">
            Sign in to development
          </button>
        </form>
      </section>
    </main>
  );
}
