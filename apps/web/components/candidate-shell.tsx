"use client";

import { UserButton } from "@clerk/nextjs";
import {
  Bell,
  BrainCircuit,
  BriefcaseBusiness,
  Radio,
  Gift,
  CircleUserRound,
  Home,
  IdCard,
  LogOut,
  Menu,
  X,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { signOutAction } from "@/app/auth/actions";
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
  { href: "/job-radar", label: "Job Radar", icon: Radio, activePrefixes: ["/job-radar"] },
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
    activePrefixes: ["/career", "/resume", "/network", "/analytics"],
  },
  {
    href: "/interview-prep",
    label: "Interview Prep",
    icon: BrainCircuit,
    activePrefixes: ["/interview-prep", "/interview"],
  },
  {
    href: "/portfolio",
    label: "Portfolio",
    icon: IdCard,
    activePrefixes: ["/portfolio"],
  },
  {
    href: "/referrals",
    label: "Referrals",
    icon: Gift,
    activePrefixes: ["/referrals"],
  },
  {
    href: "/profile",
    label: "Profile",
    icon: CircleUserRound,
    activePrefixes: ["/profile", "/settings", "/billing"],
  },
];

const mobilePrimary = navigation.filter((item) => ["/dashboard", "/jobs", "/applications", "/interview-prep"].includes(item.href));
const mobileMore = navigation.filter((item) => !mobilePrimary.includes(item));

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
  const router = useRouter();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreButton = useRef<HTMLButtonElement>(null);
  const morePanel = useRef<HTMLElement>(null);

  useEffect(() => {
    function keyboardNavigation(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        router.push("/jobs");
      }
      if (event.key === "Escape" && moreOpen) {
        setMoreOpen(false);
        moreButton.current?.focus();
      }
    }
    document.addEventListener("keydown", keyboardNavigation);
    return () => document.removeEventListener("keydown", keyboardNavigation);
  }, [router, moreOpen]);

  useEffect(() => {
    if (moreOpen) morePanel.current?.querySelector<HTMLAnchorElement>("a")?.focus();
  }, [moreOpen]);

  const email = session.email ?? "Candidate";
  const initial = email.charAt(0).toUpperCase();

  return (
    <div className="app-shell cx-app-shell">
      <aside className="app-sidebar cx-sidebar">
        <Link href="/dashboard" className="brand" aria-label="ApplyAI home">
          <span className="brand-mark">A</span>
          ApplyAI
        </Link>
        <p className="cx-brand-caption">CAREER COMMAND OS</p>

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
            {session.kind === "dev-test" || session.kind === "supabase" ? (
              <form action={session.kind === "supabase" ? signOutAction : devSignOut}>
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
          <Link className="top-search cx-top-search" href="/jobs" aria-keyshortcuts="Meta+K Control+K">
            <Search size={18} aria-hidden="true" />
            <span>Search roles, companies, or skills</span>
            <kbd aria-hidden="true">⌘ K</kbd>
          </Link>
          <div className="cx-topbar-actions">
            <span className="cx-private-status" title="Candidate evidence is private unless you explicitly share or publish it">
              <ShieldCheck size={14} /> Private workspace
            </span>
            <Link href="/alerts" className="cx-icon-link" aria-label="Alerts and follow-ups">
              <Bell size={19} />
            </Link>
            {session.kind === "clerk" ? <UserButton /> : null}
          </div>
        </header>
        <main className="app-main cx-app-main">{children}</main>
      </div>

      {moreOpen ? (
        <nav ref={morePanel} id="mobile-more-navigation" className="cx-mobile-more" aria-label="More mobile navigation">
          <div className="cx-mobile-more-heading">
            <strong>More destinations</strong>
            <button type="button" aria-label="Close more navigation" onClick={() => { setMoreOpen(false); moreButton.current?.focus(); }}><X size={20} /></button>
          </div>
          {mobileMore.map((item) => (
            <Link key={item.href} href={item.href} aria-current={isActive(pathname, item) ? "page" : undefined} onClick={() => setMoreOpen(false)}>{item.label}</Link>
          ))}
          <Link href="/settings" onClick={() => setMoreOpen(false)}>Settings and privacy</Link>
          {session.kind === "dev-test" || session.kind === "supabase" ? (
            <form action={session.kind === "supabase" ? signOutAction : devSignOut}>
              <button type="submit" className="cx-mobile-signout"><LogOut size={18} aria-hidden="true" />Sign out</button>
            </form>
          ) : null}
        </nav>
      ) : null}

      <nav className="mobile-nav cx-mobile-nav" aria-label="Primary mobile navigation">
        {mobilePrimary.map((item) => {
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
        <button
          ref={moreButton}
          type="button"
          aria-expanded={moreOpen}
          aria-controls="mobile-more-navigation"
          aria-label="More navigation"
          className={mobileMore.some((item) => isActive(pathname, item)) ? "active" : undefined}
          onClick={() => setMoreOpen(!moreOpen)}
        >
          <Menu size={21} aria-hidden="true" />
          More
        </button>
      </nav>
    </div>
  );
}
