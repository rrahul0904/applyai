"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, Button, EmptyState, ErrorState, Field, NativeSelect, PageHeader, Skeleton } from "@/components/ui";
import { JobCard } from "@/components/job-card";
import { api } from "@/lib/api/client";

const workModes = ["", "REMOTE", "HYBRID", "ONSITE"];
const employmentTypes = ["", "FULL_TIME", "PART_TIME", "CONTRACT", "TEMPORARY"];
const seniorities = ["", "ENTRY", "MID", "SENIOR", "LEAD", "EXECUTIVE"];

function SearchFilters({
  values,
  onChange,
  onClear,
}: {
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onClear: () => void;
}) {
  return (
    <div className="filter-stack">
      <Field label="Location" htmlFor="location">
        <input className="ui-input" id="location" value={values.location} placeholder="City, state, or country" onChange={(e) => onChange("location", e.target.value)} />
      </Field>
      <Field label="Work arrangement" htmlFor="work-mode">
        <NativeSelect id="work-mode" value={values.work_mode} onChange={(e) => onChange("work_mode", e.target.value)}>
          <option value="">Any arrangement</option>
          {workModes.slice(1).map((value) => <option value={value} key={value}>{value === "ONSITE" ? "On-site" : value.charAt(0) + value.slice(1).toLowerCase()}</option>)}
        </NativeSelect>
      </Field>
      <Field label="Employment type" htmlFor="employment-type">
        <NativeSelect id="employment-type" value={values.employment_type} onChange={(e) => onChange("employment_type", e.target.value)}>
          <option value="">Any type</option>
          {employmentTypes.slice(1).map((value) => <option value={value} key={value}>{value.replace("_", " ").toLowerCase()}</option>)}
        </NativeSelect>
      </Field>
      <Field label="Seniority" htmlFor="seniority">
        <NativeSelect id="seniority" value={values.seniority} onChange={(e) => onChange("seniority", e.target.value)}>
          <option value="">Any level</option>
          {seniorities.slice(1).map((value) => <option value={value} key={value}>{value.charAt(0) + value.slice(1).toLowerCase()}</option>)}
        </NativeSelect>
      </Field>
      <Field label="Minimum salary" htmlFor="salary">
        <input className="ui-input" id="salary" min="0" step="5000" type="number" value={values.minimum_salary} placeholder="e.g. 80000" onChange={(e) => onChange("minimum_salary", e.target.value)} />
      </Field>
      <Field label="Date posted" htmlFor="posted">
        <NativeSelect id="posted" value={values.posted_within_days} onChange={(e) => onChange("posted_within_days", e.target.value)}>
          <option value="">Any time</option>
          <option value="1">Past 24 hours</option>
          <option value="7">Past week</option>
          <option value="30">Past month</option>
        </NativeSelect>
      </Field>
      <Button variant="ghost" type="button" onClick={onClear}>Clear all filters</Button>
    </div>
  );
}

export function JobsView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [keyword, setKeyword] = useState(params.get("keyword") ?? "");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const values = useMemo(() => ({
    location: params.get("location") ?? "",
    work_mode: params.get("work_mode") ?? "",
    employment_type: params.get("employment_type") ?? "",
    seniority: params.get("seniority") ?? "",
    minimum_salary: params.get("minimum_salary") ?? "",
    posted_within_days: params.get("posted_within_days") ?? "",
  }), [params]);

  const replaceParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    next.delete("cursor");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      if (keyword !== (params.get("keyword") ?? "")) replaceParam("keyword", keyword);
    }, 350);
    return () => clearTimeout(timer);
    // params intentionally retriggers only when URL is externally changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keyword]);

  const query = useInfiniteQuery({
    queryKey: ["jobs", params.toString()],
    queryFn: ({ pageParam, signal }) => {
      const next = new URLSearchParams(params);
      next.set("limit", "20");
      if (pageParam) next.set("cursor", pageParam);
      return api.jobs.search(next, signal);
    },
    initialPageParam: "",
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const jobs = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Job discovery"
        title="Find work worth pursuing."
        description="Search real backend records and refine the results around what matters to you."
      />
      <div className="jobs-toolbar">
        <div className="search-input-wrap">
          <label className="sr-only" htmlFor="job-search">Search jobs</label>
          <span aria-hidden="true">⌕</span>
          <input
            className="ui-input"
            id="job-search"
            type="search"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Title, company, skill, or keyword"
          />
        </div>
        <NativeSelect aria-label="Sort jobs" defaultValue="recent">
          <option value="recent">Most recent</option>
        </NativeSelect>
        <Button className="filter-mobile-button" variant="secondary" size="icon" aria-label="Open job filters" onClick={() => setFiltersOpen(true)}>
          <SlidersHorizontal size={18} />
        </Button>
      </div>
      <div className="job-layout">
        <aside className="ui-card filter-panel" aria-label="Job filters">
          <h2>Refine results</h2>
          <SearchFilters
            values={values}
            onChange={replaceParam}
            onClear={() => router.replace(pathname)}
          />
        </aside>
        <section aria-label="Job search results">
          <div className="results-meta">
            <span>{query.isLoading ? "Searching…" : `${jobs.length}${query.hasNextPage ? "+" : ""} jobs shown`}</span>
            <span>Newest first</span>
          </div>
          {query.isError ? (
            <ErrorState message={query.error.message} retry={() => query.refetch()} />
          ) : query.isLoading ? (
            <div className="list-stack">
              {[1, 2, 3, 4].map((item) => <Skeleton className="job-card-skeleton" key={item} />)}
            </div>
          ) : jobs.length ? (
            <>
              <div className="list-stack">{jobs.map((job) => <JobCard job={job} key={job.id} />)}</div>
              {query.hasNextPage ? (
                <div className="load-more">
                  <Button variant="secondary" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
                    {query.isFetchingNextPage ? "Loading…" : "Load more jobs"}
                  </Button>
                </div>
              ) : null}
            </>
          ) : (
            <CardEmpty onClear={() => router.replace(pathname)} />
          )}
        </section>
      </div>
      <Dialog open={filtersOpen} onOpenChange={setFiltersOpen}>
        <DialogContent title="Filter jobs" description="Narrow the catalog. Changes are saved in the page URL.">
          <SearchFilters values={values} onChange={replaceParam} onClear={() => router.replace(pathname)} />
        </DialogContent>
      </Dialog>
    </>
  );
}

function CardEmpty({ onClear }: { onClear: () => void }) {
  return (
    <div className="ui-card">
      <EmptyState
        icon={<SlidersHorizontal size={22} />}
        title="No jobs match these filters"
        description="Try a broader keyword, another location, or clear the current filters."
        action={<Button onClick={onClear}>Clear filters</Button>}
      />
    </div>
  );
}
