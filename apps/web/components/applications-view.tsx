"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BriefcaseBusiness } from "lucide-react";
import Link from "next/link";
import { Badge, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";
import { formatDate, titleCase } from "@/lib/utils";

export function ApplicationsView() {
  const applications = useQuery({
    queryKey: ["applications"],
    queryFn: ({ signal }) => api.applications.list(signal),
  });

  return (
    <>
      <PageHeader eyebrow="Applications" title="Track every opportunity in one place." description="Status changes and notes are persisted to your account and survive future sessions." />
      {applications.isError ? <ErrorState message={applications.error.message} retry={() => applications.refetch()} /> : applications.isLoading ? (
        <div className="ui-card application-list">{[1, 2, 3].map((item) => <Skeleton className="skeleton-row" key={item} />)}</div>
      ) : applications.data?.length ? (
        <div className="ui-card application-list">
          {applications.data.map((application) => (
            <Link className="application-row" href={`/applications/${application.id}`} key={application.id}>
              <div><strong className="role">{application.job.title}</strong><span className="company">{application.job.company_name} · {application.job.location ?? "Location flexible"}</span></div>
              <Badge tone={application.current_status === "OFFER" ? "success" : application.current_status === "REJECTED" ? "danger" : "info"}>{titleCase(application.current_status)}</Badge>
              <span className="activity">Updated {formatDate(application.updated_at)}</span>
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
          ))}
        </div>
      ) : (
        <div className="ui-card"><EmptyState icon={<BriefcaseBusiness size={22} />} title="No applications yet" description="Open a job and start tracking your application." action={<Link className="ui-button ui-button-primary" href="/jobs">Explore jobs</Link>} /></div>
      )}
    </>
  );
}
