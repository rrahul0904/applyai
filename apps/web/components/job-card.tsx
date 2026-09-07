"use client";

import { Bookmark, BriefcaseBusiness, MapPin, WalletCards } from "lucide-react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge, Button, Card } from "@/components/ui";
import { api, type Job } from "@/lib/api/client";
import { formatDate, formatMoney, titleCase } from "@/lib/utils";

export function JobCard({ job }: { job: Job }) {
  const queryClient = useQueryClient();
  const saving = useMutation({
    mutationFn: () =>
      job.saved ? api.savedJobs.unsave(job.id) : api.savedJobs.save(job.id),
    onSuccess: () => {
      toast.success(job.saved ? "Removed from saved jobs" : "Job saved");
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["saved-jobs"] });
    },
    onError: () => toast.error("We couldn’t update this saved job."),
  });
  const salary = formatMoney(job.minimum_compensation, job.maximum_compensation);

  return (
    <Card className="job-card">
      <div className="company-logo" aria-hidden="true">
        {job.company_name.charAt(0)}
      </div>
      <div>
        <h2><Link href={`/jobs/${job.id}`}>{job.title}</Link></h2>
        <p className="job-company">{job.company_name}</p>
        <div className="job-meta">
          {job.location ? <span><MapPin size={14} />{job.location}</span> : null}
          {job.work_mode ? <Badge tone="info">{titleCase(job.work_mode)}</Badge> : null}
          {salary ? <span><WalletCards size={14} />{salary}</span> : null}
          <span><BriefcaseBusiness size={14} />{formatDate(job.posted_at)}</span>
        </div>
        <div className="job-origin">
          {job.data_origin === "DEVELOPMENT_SEED"
            ? "Fictional development listing"
            : "Verified source listing"}
        </div>
      </div>
      <div className="job-card-actions">
        <Button
          variant="secondary"
          size="icon"
          aria-label={job.saved ? `Unsave ${job.title}` : `Save ${job.title}`}
          aria-pressed={job.saved}
          disabled={saving.isPending}
          onClick={() => saving.mutate()}
        >
          <Bookmark size={18} fill={job.saved ? "currentColor" : "none"} />
        </Button>
        <Link href={`/jobs/${job.id}`} className="ui-button ui-button-primary ui-button-small">
          Review role
        </Link>
      </div>
    </Card>
  );
}
