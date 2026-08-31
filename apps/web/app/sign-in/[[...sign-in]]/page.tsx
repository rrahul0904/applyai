import { SignIn } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { CandidateAuthShell } from "@/components/candidate-auth-shell";

export const metadata: Metadata = {
  title: "Sign in | ApplyAI",
  description: "Sign in to your private ApplyAI candidate workspace.",
  robots: { index: false, follow: false },
};

export default async function SignInPage() {
  const clerkConfigured = Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY,
  );

  if (clerkConfigured) {
    const { userId } = await auth();
    if (userId) redirect("/dashboard");
  }

  return (
    <CandidateAuthShell mode="sign-in">
      {clerkConfigured ? (
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
          <strong>Candidate sign-in is ready for Clerk configuration.</strong>
          <p>Use the interactive product demo until the Clerk tenant keys are connected.</p>
          <Link className="button" href="/demo">Open product demo</Link>
        </div>
      )}
    </CandidateAuthShell>
  );
}
