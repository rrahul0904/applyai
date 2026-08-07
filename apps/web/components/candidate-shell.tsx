"use client";

import { UserButton } from "@clerk/nextjs";
import {
  Bookmark,
  BrainCircuit,
  BriefcaseBusiness,
  CircleUserRound,
  FileText,
  Home,
  LogOut,
  Search,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { devSignOut } from "@/app/dev-login/actions";
import type { ApplyAISession } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/dashboard", label: "Home", icon: Home },
  { href: "/jobs", label: "Jobs", icon: Search },
  { href: "/career", label: "Career AI", icon: BrainCircuit },
  { href: "/saved", label: "Saved", icon: Bookmark },
  { href: "/applications", label: "Applications", icon: BriefcaseBusiness },
  { href: "/resume", label: "Resume", icon: FileText },
  { href: "/profile", label: "Profile", icon: CircleUserRound },
  { href: "/settings", label: "Settings", icon: Settings },
];

const mobileNavigation = navigation.filter((item) =>
  ["/dashboard", "/jobs", "/career", "/applications", "/profile"].includes(item.href),
);

function isActive(pathname: string, href: string) {
  return pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
}

export function CandidateShell({
  session,
  children,
}: {
  session: ApplyAISession;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const email = session.email ?? "Candidate";
  const initial = email.charAt(0).toUpperCase();

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Link href="/dashboard" className="brand" aria-label="ApplyAI home">
          <span className="brand-mark">A</span>
          ApplyAI
        </Link>
        <nav aria-label="Candidate workspace">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn("nav-link", isActive(pathname, href) && "active")}
              aria-current={isActive(pathname, href) ? "page" : undefined}
            >
              <Icon size={19} aria-hidden="true" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-user">
          <div className="sidebar-user-row">
            {session.kind === "clerk" ? (
              <UserButton />
            ) : (
              <span className="avatar" aria-hidden="true">{initial}</span>
            )}
            <div className="sidebar-user-copy">
              <strong>Candidate</strong>
              <span>{email}</span>
            </div>
            {session.kind === "dev-test" ? (
              <form action={devSignOut}>
                <button className="logout-button" type="submit" aria-label="Sign out">
                  <LogOut size={18} />
                </button>
              </form>
            ) : null}
          </div>
        </div>
      </aside>

      <div className="app-content">
        <header className="app-topbar">
          <Link className="top-search" href="/jobs">
            <Search size={18} aria-hidden="true" />
            <span>Search jobs, roles, or companies</span>
            <kbd aria-hidden="true">⌘ K</kbd>
          </Link>
          {session.kind === "clerk" ? <UserButton /> : null}
        </header>
        <main className="app-main">{children}</main>
      </div>

      <nav className="mobile-nav" aria-label="Primary mobile navigation">
        {mobileNavigation.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={isActive(pathname, href) ? "active" : undefined}
            aria-current={isActive(pathname, href) ? "page" : undefined}
          >
            <Icon size={21} aria-hidden="true" />
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
