"use client";

import { useQuery } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import Link from "next/link";
import { JobCard } from "@/components/job-card";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";

export function SavedJobsView() {
  const saved = useQuery({
    queryKey: ["saved-jobs"],
    queryFn: ({ signal }) => api.savedJobs.list(signal),
  });

  return (
    <>
      <PageHeader eyebrow="Saved jobs" title="Keep the best opportunities close." description="Everything here is persisted to your candidate account." />
      {saved.isError ? <ErrorState message={saved.error.message} retry={() => saved.refetch()} /> : saved.isLoading ? (
        <div className="list-stack">{[1, 2, 3].map((item) => <Skeleton className="job-card-skeleton" key={item} />)}</div>
      ) : saved.data?.length ? (
        <div className="list-stack">{saved.data.map((job) => <JobCard key={job.id} job={job} />)}</div>
      ) : (
        <div className="ui-card"><EmptyState icon={<Bookmark size={22} />} title="No saved jobs yet" description="Save interesting roles while searching and they will appear here." action={<Link className="ui-button ui-button-primary" href="/jobs">Search jobs</Link>} /></div>
      )}
    </>
  );
}
