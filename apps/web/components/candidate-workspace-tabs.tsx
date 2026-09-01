import Link from "next/link";
import { cn } from "@/lib/utils";

type Tab = {
  href: string;
  label: string;
};

function WorkspaceTabs({ tabs, activeHref, label }: { tabs: Tab[]; activeHref: string; label: string }) {
  return (
    <nav className="cx-workspace-tabs" aria-label={label}>
      {tabs.map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          className={cn("cx-workspace-tab", tab.href === activeHref && "active")}
          aria-current={tab.href === activeHref ? "page" : undefined}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}

export function JobWorkspaceTabs({ activeHref }: { activeHref: string }) {
  return (
    <WorkspaceTabs
      label="Job workspace"
      activeHref={activeHref}
      tabs={[
        { href: "/jobs", label: "Discover" },
        { href: "/matches", label: "Recommended" },
        { href: "/saved", label: "Saved" },
        { href: "/alerts", label: "Alerts" },
      ]}
    />
  );
}

export function CareerWorkspaceTabs({ activeHref }: { activeHref: string }) {
  return (
    <WorkspaceTabs
      label="Career coach workspace"
      activeHref={activeHref}
      tabs={[
        { href: "/career", label: "Coach" },
        { href: "/career/navigation", label: "Navigation" },
        { href: "/resume/studio", label: "Resume" },
        { href: "/portfolio", label: "Portfolio" },
        { href: "/network", label: "Network" },
        { href: "/analytics", label: "Progress" },
      ]}
    />
  );
}
