import { redirect } from "next/navigation";
import { devAuthEnabled, getApplyAISession } from "@/lib/auth/session";

export default async function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const session = await getApplyAISession();
  if (!session.authenticated) redirect(devAuthEnabled() ? "/dev-login" : "/");
  return (
    <div className="onboarding-shell">
      <header className="onboarding-top">
        <span className="brand"><span className="brand-mark">A</span>ApplyAI</span>
        <span className="configuration-label">Candidate setup</span>
      </header>
      {children}
    </div>
  );
}
