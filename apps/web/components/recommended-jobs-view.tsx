"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Sparkles } from "lucide-react";
import Link from "next/link";
import { JobWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";
import { platformApi } from "@/lib/api/platform-client";
import { titleCase } from "@/lib/utils";

function recommendationLabel(decision?: string) {
  if (!decision) return "Recommended";
  switch (decision.toUpperCase()) {
    case "APPLY_NOW": return "Apply now";
    case "STRONG": return "Strong fit";
    case "CONSIDER": return "Worth considering";
    case "LOW_PRIORITY": return "Lower priority";
    case "REJECT": return "Not recommended";
    default: return titleCase(decision);
  }
}

export function RecommendedJobsView() {
  const semantic = useQuery({ queryKey: ["semantic-matches"], queryFn: () => platformApi.semanticMatches(40) });
  const career = useQuery({ queryKey: ["career-v2-matches"], queryFn: ({ signal }) => api.careerV2.matches(signal), retry: false });

  if (semantic.isLoading || career.isLoading) return <Skeleton className="page-skeleton" />;
  if (semantic.isError) return <ErrorState message={semantic.error.message} retry={() => semantic.refetch()} />;

  const careerByJob = new Map((career.data?.items ?? []).map((item) => [item.job_id, item]));
  const items = [...(semantic.data?.items ?? [])].sort((a, b) => {
    const scoreA = careerByJob.get(a.job_id)?.final_score ?? a.semantic_score;
    const scoreB = careerByJob.get(b.job_id)?.final_score ?? b.semantic_score;
    return scoreB - scoreA;
  });

  return (
    <>
      <JobWorkspaceTabs activeHref="/matches" />
      <PageHeader
        eyebrow="Recommended for you"
        title="Start with the roles that fit best."
        description="We combine your goals, preferences, and verified experience to help you spend time on the opportunities most worth pursuing."
      />

      {items.length ? (
        <div className="cx-recommendation-list">
          {items.map((item, index) => {
            const match = careerByJob.get(item.job_id);
            const score = Math.max(0, Math.round(match?.final_score ?? item.semantic_score));
            const tone = match?.decision?.toUpperCase() === "APPLY_NOW" || match?.decision?.toUpperCase() === "STRONG" ? "success" : "info";
            return (
              <Card key={item.job_id} className="cx-recommendation-card">
                <div className="cx-rank" aria-label={`Recommendation ${index + 1}`}>{index + 1}</div>
                <div className="cx-recommendation-main">
                  <div className="cx-recommendation-heading">
                    <div>
                      <p className="cx-action-label">{item.company}</p>
                      <h2>{item.title}</h2>
                    </div>
                    <div className="cx-match-summary">
                      <strong>{score}%</strong>
                      <span>match</span>
                    </div>
                  </div>
                  <div className="cx-recommendation-badges">
                    <Badge tone={tone}>{recommendationLabel(match?.decision)}</Badge>
                    {match?.fit_band ? <Badge>{titleCase(match.fit_band)} fit</Badge> : null}
                    {match?.confidence ? <span className="cx-confidence">{titleCase(match.confidence)} confidence</span> : null}
                  </div>
                  <p className="cx-recommendation-explanation">{item.explanation}</p>
                  <div className="cx-trust-note"><CheckCircle2 size={16} /><span>Recommendation is based on your verified profile and preferences—not a hiring probability.</span></div>
                </div>
                <div className="cx-recommendation-actions">
                  <Link className="ui-button ui-button-primary" href={`/jobs/${item.job_id}`}>Review & prepare <ArrowRight size={16} /></Link>
                  <Link className="ui-button ui-button-ghost ui-button-small" href={`/interview/${item.job_id}`}><Sparkles size={15} />Interview prep</Link>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Sparkles size={22} />}
            title="Your recommendations are getting ready"
            description="Complete your profile and career evidence so ApplyAI can prioritize active roles around what matters to you."
            action={<Link className="ui-button ui-button-primary" href="/profile">Complete profile</Link>}
          />
        </Card>
      )}
    </>
  );
}
