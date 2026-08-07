"use client";

import { BriefcaseBusiness, Home, LogOut, UsersRound } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { devSignOut } from "@/app/dev-login/actions";
import type { ApplyAISession } from "@/lib/auth/session";

export function EmployerShell({ session, children }: { session: ApplyAISession; children: ReactNode }) {
  return <div className="app-shell">
    <aside className="app-sidebar">
      <Link href="/employer" className="brand"><span className="brand-mark">A</span>ApplyAI Hire</Link>
      <nav aria-label="Employer workspace">
        <Link className="nav-link" href="/employer"><Home size={19}/>Overview</Link>
        <Link className="nav-link" href="/employer#jobs"><BriefcaseBusiness size={19}/>Jobs</Link>
        <Link className="nav-link" href="/employer#applicants"><UsersRound size={19}/>Applicants</Link>
        <Link className="nav-link" href="/dashboard">Candidate workspace</Link>
      </nav>
      {session.kind === "dev-test" ? <form action={devSignOut}><button className="logout-button" type="submit"><LogOut size={18}/> Sign out</button></form> : null}
    </aside>
    <div className="app-content"><header className="app-topbar"><strong>{session.email ?? "Employer"}</strong></header><main className="app-main">{children}</main></div>
  </div>;
}
