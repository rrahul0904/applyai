import { redirect } from "next/navigation";
import { EmployerShell } from "@/components/employer-shell";
import { devAuthEnabled, getApplyAISession } from "@/lib/auth/session";

export default async function EmployerLayout({ children }: { children: React.ReactNode }) {
  const session = await getApplyAISession();
  if (!session.authenticated) redirect(devAuthEnabled() ? "/dev-login" : "/");
  return <EmployerShell session={session}>{children}</EmployerShell>;
}
