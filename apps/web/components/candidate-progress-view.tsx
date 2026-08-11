"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Bookmark, BriefcaseBusiness, FileText, MessageCircle, UsersRound } from "lucide-react";
import { CareerWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { Card, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { platformApi } from "@/lib/api/platform-client";
import { titleCase } from "@/lib/utils";

function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function CandidateProgressView() {
  const analytics = useQuery({ queryKey: ["candidate-analytics"], queryFn: platformApi.analytics });
  if (analytics.isLoading) return <Skeleton className="page-skeleton" />;
  if (analytics.isError) return <ErrorState message={analytics.error.message} retry={() => analytics.refetch()} />;

  const data = analytics.data ?? {};
  const applications = typeof data.applications === "object" && data.applications !== null
    ? data.applications as Record<string, unknown>
    : {};
  const stages = Object.entries(applications)
    .map(([stage, value]) => [stage, numberValue(value)] as const)
    .filter(([, value]) => value > 0);
  const maxStage = Math.max(1, ...stages.map(([, value]) => value));

  const cards = [
    { label: "Saved roles", value: numberValue(data.saved_jobs), icon: Bookmark, note: "Opportunities on your shortlist" },
    { label: "Resume versions", value: numberValue(data.resume_documents), icon: FileText, note: "Tailored documents you can revisit" },
    { label: "Interview practices", value: numberValue(data.interview_practice_sessions), icon: MessageCircle, note: "Preparation sessions completed" },
    { label: "Network contacts", value: numberValue(data.network_contacts), icon: UsersRound, note: "Career relationships you're tracking" },
  ];

  return (
    <>
      <CareerWorkspaceTabs activeHref="/analytics" />
      <PageHeader
        eyebrow="Your progress"
        title="See where your search is moving."
        description="A simple view of the activity behind your job search—without turning your career into a dashboard full of noise."
      />

      <div className="cx-progress-grid">
        {cards.map(({ label, value, icon: Icon, note }) => (
          <Card className="cx-progress-card" key={label}>
            <div className="cx-progress-icon"><Icon size={18} /></div>
            <strong>{value}</strong>
            <span>{label}</span>
            <p>{note}</p>
          </Card>
        ))}
      </div>

      <Card className="cx-funnel-card">
        <div className="cx-section-heading compact">
          <div><p className="eyebrow">Application momentum</p><h2>Your pipeline</h2></div>
          <div className="cx-funnel-summary"><BriefcaseBusiness size={17} />{stages.reduce((total, [, value]) => total + value, 0)} tracked</div>
        </div>
        {stages.length ? (
          <div className="cx-funnel-list">
            {stages.map(([stage, value]) => (
              <div className="cx-funnel-row" key={stage}>
                <div><strong>{titleCase(stage)}</strong><span>{value}</span></div>
                <div className="cx-funnel-track"><div style={{ width: `${Math.max(8, (value / maxStage) * 100)}%` }} /></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="cx-gentle-empty"><BarChart3 size={20} /><p>Your application pipeline will appear here after you start preparing and tracking roles.</p></div>
        )}
      </Card>
    </>
  );
}
