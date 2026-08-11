"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { ArrowRight, BriefcaseBusiness } from "lucide-react";
import Link from "next/link";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";
import { formatDate, titleCase } from "@/lib/utils";

export function ApplicationsView() {
  const applications = useInfiniteQuery({
    queryKey: ["applications"],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) => api.applications.list(signal, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const items = applications.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Applications"
        title="Keep every opportunity moving."
        description="See what needs attention, what changed, and where to pick up next."
        action={<Link className="ui-button ui-button-primary" href="/jobs">Find roles</Link>}
      />
      {applications.isError ? <ErrorState message={applications.error.message} retry={() => applications.refetch()} /> : applications.isLoading ? (
        <div className="ui-card application-list">{[1, 2, 3].map((item) => <Skeleton className="skeleton-row" key={item} />)}</div>
      ) : items.length ? (
        <>
          <div className="ui-card application-list">
            {items.map((application) => (
              <Link className="application-row" href={`/applications/${application.id}`} key={application.id}>
                <div><strong className="role">{application.job.title}</strong><span className="company">{application.job.company_name} · {application.job.location ?? "Location flexible"}</span></div>
                <Badge tone={application.current_status === "OFFER" ? "success" : application.current_status === "REJECTED" ? "danger" : "info"}>{titleCase(application.current_status)}</Badge>
                <span className="activity">Updated {formatDate(application.updated_at)}</span>
                <ArrowRight size={17} aria-hidden="true" />
              </Link>
            ))}
          </div>
          {applications.hasNextPage ? (
            <div className="button-row" style={{ marginTop: 16 }}>
              <Button variant="secondary" disabled={applications.isFetchingNextPage} onClick={() => applications.fetchNextPage()}>
                {applications.isFetchingNextPage ? "Loading…" : "Show more applications"}
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <div className="ui-card"><EmptyState icon={<BriefcaseBusiness size={22} />} title="No applications yet" description="When a role looks promising, choose Prepare application from the job page and it will appear here." action={<Link className="ui-button ui-button-primary" href="/jobs">Explore jobs</Link>} /></div>
      )}
    </>
  );
}
