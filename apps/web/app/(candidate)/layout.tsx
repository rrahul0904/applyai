import { redirect } from "next/navigation";
import { CandidateShell } from "@/components/candidate-shell";
import { devAuthEnabled, getApplyAISession } from "@/lib/auth/session";

export default async function CandidateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getApplyAISession();
  if (!session.authenticated) {
    redirect(devAuthEnabled() ? "/dev-login" : "/sign-in");
  }
  return <CandidateShell session={session}>{children}</CandidateShell>;
}
