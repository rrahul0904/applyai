import { Suspense } from "react";
import { JobsView } from "@/components/jobs-view";
import { Skeleton } from "@/components/ui";

export default function JobsPage() {
  return (
    <Suspense fallback={<Skeleton className="page-skeleton" />}>
      <JobsView />
    </Suspense>
  );
}
