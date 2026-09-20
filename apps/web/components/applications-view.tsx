"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BriefcaseBusiness, CalendarDays } from "lucide-react";
import Link from "next/link";
import { ApplicationWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { Badge, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api, type ApplicationBoardItem } from "@/lib/api/client";
import { formatDate, titleCase } from "@/lib/utils";

const stageOrder = [
  "PREPARING",
  "READY",
  "APPLIED",
  "RECRUITER_SCREEN",
  "ASSESSMENT",
  "INTERVIEW",
  "FINAL_INTERVIEW",
  "OFFER",
  "REJECTED",
  "WITHDRAWN",
];

function trackerLine(item: ApplicationBoardItem) {
  const parts: string[] = [];
  if (item.tracker.next_action_at) parts.push(`Next ${formatDate(item.tracker.next_action_at)}`);
  if (item.tracker.interview_at) parts.push(`Interview ${formatDate(item.tracker.interview_at)}`);
  if (item.tracker.deadline_at) parts.push(`Deadline ${formatDate(item.tracker.deadline_at)}`);
  if (item.tracker.source_channel) parts.push(item.tracker.source_channel);
  return parts.join(" · ");
}

export function ApplicationsView() {
  const board = useQuery({
    queryKey: ["applications", "board"],
    queryFn: ({ signal }) => api.applications.board(signal),
  });

  const items = board.data?.items ?? [];
  const grouped = stageOrder
    .map((stage) => [stage, items.filter((item) => item.current_status === stage)] as const)
    .filter(([, rows]) => rows.length > 0);

  return (
    <>
      <ApplicationWorkspaceTabs activeHref="/applications" />
      <PageHeader
        eyebrow="Opportunity CRM"
        title="Keep every opportunity moving."
        description="A stage-first pipeline for applications, interviews, follow-ups, deadlines, and offers."
        action={<Link className="ui-button ui-button-primary" href="/jobs">Find roles</Link>}
      />
      {board.isError ? (
        <ErrorState message={board.error.message} retry={() => board.refetch()} />
      ) : board.isLoading ? (
        <div className="ui-card application-list">
          {[1, 2, 3].map((item) => <Skeleton className="skeleton-row" key={item} />)}
        </div>
      ) : items.length ? (
        <div className="list-stack" aria-label="Opportunity pipeline board">
          <div className="cx-application-status-strip">
            <span>{board.data?.total ?? 0} opportunities</span>
            <span>{items.filter((item) => item.overdue).length} overdue deadlines</span>
            <span>{board.data?.counts.OFFER ?? 0} offers</span>
          </div>
          {grouped.map(([stage, rows]) => (
            <section className="ui-card" key={stage}>
              <div className="section-header">
                <div>
                  <h2>{titleCase(stage)}</h2>
                  <p>{rows.length} {rows.length === 1 ? "opportunity" : "opportunities"} in this stage.</p>
                </div>
                <Badge tone={stage === "OFFER" ? "success" : stage === "REJECTED" ? "danger" : "info"}>
                  {rows.length}
                </Badge>
              </div>
              <div className="application-list">
                {rows.map((application) => {
                  const tracker = trackerLine(application);
                  return (
                    <Link
                      className="application-row"
                      href={`/applications/${application.id}`}
                      key={application.id}
                    >
                      <div>
                        <strong className="role">{application.job.title}</strong>
                        <span className="company">
                          {application.job.company_name} · {application.job.location ?? "Location flexible"}
                        </span>
                        {tracker ? <span className="activity">{tracker}</span> : null}
                      </div>
                      <Badge tone={application.overdue ? "danger" : application.tracker.priority === "HIGH" ? "warning" : "info"}>
                        {application.overdue ? "Overdue" : titleCase(application.tracker.priority)}
                      </Badge>
                      <span className="activity">
                        <CalendarDays size={14} aria-hidden="true" /> Updated {formatDate(application.updated_at)}
                      </span>
                      <ArrowRight size={17} aria-hidden="true" />
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="ui-card">
          <EmptyState
            icon={<BriefcaseBusiness size={22} />}
            title="No active opportunities yet"
            description="Save roles casually. Start an application when you decide the opportunity deserves active preparation and follow-up."
            action={<Link className="ui-button ui-button-primary" href="/jobs">Explore jobs</Link>}
          />
        </div>
      )}
    </>
  );
}
