"use client";

import { UserButton } from "@clerk/nextjs";
import {
  Bell,
  BriefcaseBusiness,
  CircleUserRound,
  CreditCard,
  Home,
  LogOut,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { devSignOut } from "@/app/dev-login/actions";
import type { ApplyAISession } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

type NavigationItem = {
  href: string;
  label: string;
  icon: typeof Home;
  activePrefixes: string[];
};

const navigation: NavigationItem[] = [
  { href: "/dashboard", label: "Home", icon: Home, activePrefixes: ["/dashboard"] },
  {
    href: "/jobs",
    label: "Jobs",
    icon: Search,
    activePrefixes: ["/jobs", "/matches", "/saved", "/alerts", "/import-job"],
  },
  {
    href: "/applications",
    label: "Applications",
    icon: BriefcaseBusiness,
    activePrefixes: ["/applications"],
  },
  {
    href: "/career",
    label: "Career Coach",
    icon: Sparkles,
    activePrefixes: ["/career", "/resume", "/network", "/interview", "/analytics"],
  },
  {
    href: "/profile",
    label: "Profile",
    icon: CircleUserRound,
    activePrefixes: ["/profile", "/settings", "/billing"],
  },
];

function isActive(pathname: string, item: NavigationItem) {
  return item.activePrefixes.some((prefix) =>
    pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
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
    <div className="app-shell cx-app-shell">
      <aside className="app-sidebar cx-sidebar">
        <Link href="/dashboard" className="brand" aria-label="ApplyAI home">
          <span className="brand-mark">A</span>
          ApplyAI
        </Link>
        <p className="cx-brand-caption">Your career, in motion.</p>

        <nav aria-label="Candidate workspace" className="cx-primary-nav">
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn("nav-link", "cx-nav-link", active && "active")}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={19} aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-user cx-sidebar-user">
          <div className="cx-account-links" aria-label="Account shortcuts">
            <Link href="/billing"><CreditCard size={15} />Plan</Link>
            <Link href="/settings"><Settings size={15} />Settings</Link>
          </div>
          <div className="sidebar-user-row">
            {session.kind === "clerk" ? (
              <UserButton />
            ) : (
              <span className="avatar" aria-hidden="true">{initial}</span>
            )}
            <div className="sidebar-user-copy">
              <strong>Your account</strong>
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

      <div className="app-content cx-app-content">
        <header className="app-topbar cx-topbar">
          <Link className="top-search cx-top-search" href="/jobs">
            <Search size={18} aria-hidden="true" />
            <span>Search roles or companies</span>
            <kbd aria-hidden="true">⌘ K</kbd>
          </Link>
          <div className="cx-topbar-actions">
            <Link href="/alerts" className="cx-icon-link" aria-label="Alerts and follow-ups">
              <Bell size={19} />
            </Link>
            {session.kind === "clerk" ? <UserButton /> : null}
          </div>
        </header>
        <main className="app-main cx-app-main">{children}</main>
      </div>

      <nav className="mobile-nav cx-mobile-nav" aria-label="Primary mobile navigation">
        {navigation.map((item) => {
          const Icon = item.icon;
          const active = isActive(pathname, item);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={active ? "active" : undefined}
              aria-current={active ? "page" : undefined}
            >
              <Icon size={21} aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
