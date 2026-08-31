import { SignUp } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { redirect } from "next/navigation";
import { CandidateAuthShell } from "@/components/candidate-auth-shell";

export default async function SignUpPage() {
  const clerkConfigured = Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY,
  );

  if (clerkConfigured) {
    const { userId } = await auth();
    if (userId) redirect("/dashboard");
  }

  return (
    <CandidateAuthShell mode="sign-up">
      {clerkConfigured ? (
        <SignUp
          path="/sign-up"
          routing="path"
          signInUrl="/sign-in"
          fallbackRedirectUrl="/onboarding"
          signInFallbackRedirectUrl="/dashboard"
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
          <strong>Account creation is ready for Clerk configuration.</strong>
          <p>Use the interactive product demo until the Clerk tenant keys are connected.</p>
          <Link className="button" href="/demo">Open product demo</Link>
        </div>
      )}
    </CandidateAuthShell>
  );
}
