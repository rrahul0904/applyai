"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import Link from "next/link";
import { JobWorkspaceTabs } from "@/components/candidate-workspace-tabs";
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
      <JobWorkspaceTabs activeHref="/saved" />
      <PageHeader eyebrow="Your shortlist" title="Keep the roles worth comparing." description="Save interesting opportunities here without losing focus on what needs your attention today." />
      {saved.isError ? <ErrorState message={saved.error.message} retry={() => saved.refetch()} /> : saved.isLoading ? (
        <div className="list-stack">{[1, 2, 3].map((item) => <Skeleton className="job-card-skeleton" key={item} />)}</div>
      ) : items.length ? (
        <>
          <div className="list-stack">{items.map((job) => <JobCard key={job.id} job={job} />)}</div>
          {saved.hasNextPage ? (
            <div className="button-row" style={{ marginTop: 16 }}>
              <Button variant="secondary" disabled={saved.isFetchingNextPage} onClick={() => saved.fetchNextPage()}>
                {saved.isFetchingNextPage ? "Loading…" : "Show more saved roles"}
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <div className="ui-card"><EmptyState icon={<Bookmark size={22} />} title="Your shortlist is empty" description="Save roles you want to compare and revisit. ApplyAI will keep them here without cluttering your recommendations." action={<Link className="ui-button ui-button-primary" href="/jobs">Explore jobs</Link>} /></div>
      )}
    </>
  );
}
