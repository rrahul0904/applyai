import { SignIn } from "@clerk/nextjs";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { CandidateAuthShell } from "@/components/candidate-auth-shell";
import { SupabaseAuthForm } from "@/components/supabase-auth-form";
import { getApplyAISession } from "@/lib/auth/session";
import { supabaseConfigured } from "@/lib/auth/supabase-http";

export const metadata: Metadata = {
  title: "Sign in | ApplyAI",
  description: "Sign in to your private ApplyAI candidate workspace.",
  robots: { index: false, follow: false },
};

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await getApplyAISession();
  if (session.authenticated) redirect("/dashboard");

  const params = await searchParams;
  const error = typeof params.error === "string" ? params.error : undefined;
  const checkEmail = params.check_email === "1";
  const useSupabase = supabaseConfigured();
  const clerkConfigured =
    !useSupabase &&
    Boolean(
      process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY,
    );

  return (
    <CandidateAuthShell mode="sign-in">
      {useSupabase ? (
        <SupabaseAuthForm
          mode="sign-in"
          error={error}
          checkEmail={false}
        />
      ) : clerkConfigured ? (
        <SignIn
          path="/sign-in"
          routing="path"
          signUpUrl="/sign-up"
          fallbackRedirectUrl="/dashboard"
          signUpFallbackRedirectUrl="/onboarding"
          appearance={{
            variables: {
              colorPrimary: "#173d30",
              colorText: "#17231d",
              colorTextSecondary: "#667169",
              colorBackground: "#ffffff",
              borderRadius: "12px",
            },
          }}
        />
      ) : (
        <div className="empty-state">
          <strong>Candidate sign-in is awaiting identity configuration.</strong>
          <p>Use the interactive product demo until the production identity provider is connected.</p>
          <Link className="button" href="/demo">Open product demo</Link>
        </div>
      )}
    </CandidateAuthShell>
  );
}
