"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  MapPin,
  WalletCards,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { CareerIntelligencePanel } from "@/components/career-intelligence-panel";
import { api } from "@/lib/api/client";
import { Badge, Button, Card, ErrorState, Skeleton } from "@/components/ui";
import { formatDate, formatMoney, titleCase } from "@/lib/utils";

export function JobDetailView({ jobId }: { jobId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: ({ signal }) => api.jobs.detail(jobId, signal),
  });
  const saving = useMutation({
    mutationFn: () =>
      job.data?.saved ? api.savedJobs.unsave(jobId) : api.savedJobs.save(jobId),
    onSuccess: async () => {
      toast.success(job.data?.saved ? "Removed from saved jobs" : "Job saved");
      await queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      await queryClient.invalidateQueries({ queryKey: ["saved-jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: () => toast.error("We couldn't update this saved job."),
  });
  const applying = useMutation({
    mutationFn: () => api.applications.create(jobId),
    onSuccess: (application) => {
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      router.push(`/applications/${application.id}`);
    },
    onError: () => toast.error("We couldn't start tracking this application."),
  });

  if (job.isLoading) return <Skeleton className="page-skeleton" />;
  if (job.isError || !job.data) {
    return <ErrorState message={job.error?.message} retry={() => job.refetch()} />;
  }

  const item = job.data;
  const salary = formatMoney(item.minimum_compensation, item.maximum_compensation);
  return (
    <div className="detail-grid">
      <div className="detail-main">
        <Card className="detail-hero">
          <div className="detail-title-row">
            <div className="company-logo" aria-hidden="true">
              {item.company_name.charAt(0)}
            </div>
            <div>
              <p className="eyebrow">
                {item.data_origin === "DEVELOPMENT_SEED"
                  ? "Development data"
                  : "Job opportunity"}
              </p>
              <h1>{item.title}</h1>
              <p className="job-company">{item.company_name}</p>
              <div className="job-meta">
                {item.location ? (
                  <span>
                    <MapPin size={15} />
                    {item.location}
                  </span>
                ) : null}
                {item.work_mode ? (
                  <Badge tone="info">{titleCase(item.work_mode)}</Badge>
                ) : null}
                {item.employment_type ? (
                  <span>
                    <BriefcaseBusiness size={15} />
                    {titleCase(item.employment_type)}
                  </span>
                ) : null}
                {salary ? (
                  <span>
                    <WalletCards size={15} />
                    {salary}
                  </span>
                ) : null}
              </div>
            </div>
          </div>
        </Card>

        <CareerIntelligencePanel jobId={jobId} />

        <Card className="detail-section">
          <h2>About the role</h2>
          <div className="detail-copy">{item.description}</div>
        </Card>

        {item.requirements.length ? (
          <Card className="detail-section">
            <h2>Requirements</h2>
            <ul>
              {item.requirements.map((requirement) => (
                <li key={requirement}>{requirement}</li>
              ))}
            </ul>
          </Card>
        ) : null}
        {item.skills.length ? (
          <Card className="detail-section">
            <h2>Skills</h2>
            <div className="chips">
              {item.skills.map((skill) => (
                <Badge key={skill}>{skill}</Badge>
              ))}
            </div>
          </Card>
        ) : null}
      </div>

      <aside className="detail-aside">
        <Card className="sticky-actions">
          <Button onClick={() => applying.mutate()} disabled={applying.isPending}>
            Track application
          </Button>
          <Button
            variant="secondary"
            onClick={() => saving.mutate()}
            disabled={saving.isPending}
            aria-pressed={item.saved}
          >
            <Bookmark size={17} fill={item.saved ? "currentColor" : "none"} />
            {item.saved ? "Saved" : "Save job"}
          </Button>
          <div className="facts-list">
            <div className="fact-row">
              <Building2 size={17} />
              <div>
                <strong>Company</strong>
                <span>{item.company_name}</span>
              </div>
            </div>
            <div className="fact-row">
              <CalendarDays size={17} />
              <div>
                <strong>Posted</strong>
                <span>{formatDate(item.posted_at)}</span>
              </div>
            </div>
            <div className="fact-row">
              <CalendarDays size={17} />
              <div>
                <strong>Last verified</strong>
                <span>{formatDate(item.last_seen_at)}</span>
              </div>
            </div>
          </div>
          {item.source_url ? (
            <a
              className="ui-button ui-button-ghost ui-button-small"
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
            >
              Open source listing
            </a>
          ) : null}
        </Card>
      </aside>
    </div>
  );
}
