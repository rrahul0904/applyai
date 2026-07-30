"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bookmark, BriefcaseBusiness, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SectionHeader,
  Skeleton,
} from "@/components/ui";
import { api } from "@/lib/api/client";
import { formatDate, titleCase } from "@/lib/utils";

export function DashboardView() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const me = useQuery({ queryKey: ["me"], queryFn: ({ signal }) => api.auth.me(signal) });
  const jobs = useQuery({
    queryKey: ["jobs", "dashboard"],
    queryFn: ({ signal }) => api.jobs.search(new URLSearchParams({ limit: "4" }), signal),
  });
  const saved = useQuery({
    queryKey: ["saved-jobs", "dashboard"],
    queryFn: ({ signal }) => api.savedJobs.list(signal),
  });
  const applications = useQuery({
    queryKey: ["applications", "dashboard"],
    queryFn: ({ signal }) => api.applications.list(signal),
  });
  const savedItems = saved.data?.items ?? [];
  const applicationItems = applications.data?.items ?? [];

  useEffect(() => {
    if (me.data && !me.data.onboarding_completed) router.replace("/onboarding");
  }, [me.data, router]);

  if (me.isError || jobs.isError || saved.isError || applications.isError) {
    return <ErrorState retry={() => location.reload()} />;
  }
  return (
    <>
      <PageHeader
        eyebrow="Your workspace"
        title="Make your next move count."
        description="Pick up your search, revisit promising roles, and keep applications moving."
      />
      <div className="dashboard-grid">
        <div className="dashboard-stack">
          <Card className="dashboard-panel">
            <SectionHeader
              title="Continue your search"
              description="Search the current canonical job catalog."
            />
            <form
              className="quick-search"
              onSubmit={(event) => {
                event.preventDefault();
                router.push(query ? `/jobs?keyword=${encodeURIComponent(query)}` : "/jobs");
              }}
            >
              <label className="sr-only" htmlFor="dashboard-search">Search jobs</label>
              <input
                className="ui-input"
                id="dashboard-search"
                placeholder="Job title, skill, or company"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button className="ui-button ui-button-primary" type="submit">
                <Search size={17} /> Search
              </button>
            </form>
          </Card>

          <Card className="dashboard-panel">
            <SectionHeader
              title="Recent jobs"
              description="Fresh roles from the searchable catalog."
              action={<Link href="/jobs" className="text-button">View all <ArrowRight size={14} /></Link>}
            />
            {jobs.isLoading ? (
              <div className="list-stack">
                {[1, 2, 3].map((item) => <Skeleton key={item} className="skeleton-row" />)}
              </div>
            ) : (
              <div className="list-stack">
                {jobs.data?.items.map((job) => (
                  <Link className="application-row" href={`/jobs/${job.id}`} key={job.id}>
                    <div>
                      <strong className="role">{job.title}</strong>
                      <span className="company">{job.company_name} · {job.location ?? "Location flexible"}</span>
                    </div>
                    <Badge tone="info">{titleCase(job.work_mode ?? "Flexible")}</Badge>
                    <span className="activity">{formatDate(job.posted_at)}</span>
                    <ArrowRight size={17} />
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="dashboard-stack">
          <Card className="dashboard-panel">
            <SectionHeader
              title="Saved jobs"
              action={<Link href="/saved" className="text-button">See all</Link>}
            />
            {saved.isLoading ? <Skeleton className="skeleton-tall" /> : savedItems.length ? (
              <div className="list-stack">
                {savedItems.slice(0, 3).map((job) => (
                  <Link className="nav-link" href={`/jobs/${job.id}`} key={job.id}>
                    <Bookmark size={17} />
                    <span>{job.title}<small className="muted"> · {job.company_name}</small></span>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<Bookmark size={22} />}
                title="No saved jobs yet"
                description="Save promising opportunities and they’ll appear here."
                action={<Link className="ui-button ui-button-secondary ui-button-small" href="/jobs">Browse jobs</Link>}
              />
            )}
          </Card>
          <Card className="dashboard-panel">
            <SectionHeader
              title="Applications"
              action={<Link href="/applications" className="text-button">See all</Link>}
            />
            {applications.isLoading ? <Skeleton className="skeleton-tall" /> : applicationItems.length ? (
              <div className="list-stack">
                {applicationItems.slice(0, 4).map((application) => (
                  <Link className="nav-link" href={`/applications/${application.id}`} key={application.id}>
                    <BriefcaseBusiness size={17} />
                    <span>{titleCase(application.current_status)}<small className="muted"> · updated {formatDate(application.updated_at)}</small></span>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<BriefcaseBusiness size={22} />}
                title="No applications yet"
                description="Track every opportunity from preparation through offer."
                action={<Link className="ui-button ui-button-secondary ui-button-small" href="/jobs">Explore jobs</Link>}
              />
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
