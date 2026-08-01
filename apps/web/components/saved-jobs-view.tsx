"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import Link from "next/link";
import { JobCard } from "@/components/job-card";
import { Button, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";

export function SavedJobsView() {
  const saved = useInfiniteQuery({
    queryKey: ["saved-jobs"],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) => api.savedJobs.list(signal, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const items = saved.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <PageHeader eyebrow="Saved jobs" title="Keep the best opportunities close." description="Everything here is persisted to your candidate account." />
      {saved.isError ? <ErrorState message={saved.error.message} retry={() => saved.refetch()} /> : saved.isLoading ? (
        <div className="list-stack">{[1, 2, 3].map((item) => <Skeleton className="job-card-skeleton" key={item} />)}</div>
      ) : items.length ? (
        <>
          <div className="list-stack">{items.map((job) => <JobCard key={job.id} job={job} />)}</div>
          {saved.hasNextPage ? (
            <div className="button-row" style={{ marginTop: 16 }}>
              <Button variant="secondary" disabled={saved.isFetchingNextPage} onClick={() => saved.fetchNextPage()}>
                {saved.isFetchingNextPage ? "Loading…" : "Load more saved jobs"}
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <div className="ui-card"><EmptyState icon={<Bookmark size={22} />} title="No saved jobs yet" description="Save interesting roles while searching and they will appear here." action={<Link className="ui-button ui-button-primary" href="/jobs">Search jobs</Link>} /></div>
      )}
    </>
  );
}
