"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Radar, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";
import { JobWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";
import { platformApi } from "@/lib/api/platform-client";
import { titleCase } from "@/lib/utils";

function recommendationLabel(decision?: string | null) {
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
  const queryClient = useQueryClient();
  const semantic = useQuery({ queryKey: ["semantic-matches"], queryFn: () => platformApi.semanticMatches(40) });
  const career = useQuery({ queryKey: ["career-v2-matches"], queryFn: ({ signal }) => api.careerV2.matches(signal), retry: false });
  const radar = useQuery({
    queryKey: ["career-v2-radar"],
    queryFn: ({ signal }) => api.careerV2.radar(signal),
    retry: false,
    refetchInterval: 30_000,
  });
  const watches = useQuery({
    queryKey: ["career-v2-radar-watches"],
    queryFn: ({ signal }) => api.careerV2.radarWatches(signal),
    retry: false,
  });
  const radarHistory = useQuery({
    queryKey: ["career-v2-radar-history"],
    queryFn: ({ signal }) => api.careerV2.radarHistory(signal),
    retry: false,
  });
  const refreshRadar = useMutation({
    mutationFn: () => api.careerV2.refreshRadar(),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["career-v2-radar"] }),
        queryClient.invalidateQueries({ queryKey: ["career-v2-matches"] }),
      ]);
    },
  });
  const toggleWatch = useMutation({
    mutationFn: async () => {
      const watch = watches.data?.items[0];
      if (!watch) {
        return api.careerV2.createRadarWatch({
          name: "Daily job radar",
          interval_minutes: 1440,
          lookback_days: 14,
          max_jobs: 5,
          run_immediately: true,
        });
      }
      return api.careerV2.updateRadarWatch(watch.id, { enabled: !watch.enabled });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["career-v2-radar-watches"] });
    },
  });

  if (semantic.isLoading || career.isLoading) return <Skeleton className="page-skeleton" />;
  if (semantic.isError) return <ErrorState message={semantic.error.message} retry={() => semantic.refetch()} />;

  const careerByJob = new Map((career.data?.items ?? []).map((item) => [item.job_id, item]));
  const items = [...(semantic.data?.items ?? [])].sort((a, b) => {
    const scoreA = careerByJob.get(a.job_id)?.final_score ?? a.semantic_score;
    const scoreB = careerByJob.get(b.job_id)?.final_score ?? b.semantic_score;
    return scoreB - scoreA;
  });
  const activeWatch = watches.data?.items[0];
  const radarItems = (radar.data?.items ?? [])
    .filter((item) => item.radar_bucket === "TOP_MATCH" || item.radar_bucket === "PENDING_JUDGMENT")
    .slice(0, 4);

  return (
    <>
      <JobWorkspaceTabs activeHref="/matches" />
      <PageHeader
        eyebrow="Recommended for you"
        title="Start with the roles that fit best."
        description="We combine your goals, preferences, and verified experience to help you spend time on the opportunities most worth pursuing."
      />

      <Card>
        <div className="cx-recommendation-heading">
          <div>
            <p className="cx-action-label"><Radar size={15} /> ApplyAI Job Radar</p>
            <h2>Fresh roles, judged before you scroll.</h2>
            <p className="cx-recommendation-explanation">
              Radar reviews newly discovered jobs against your verified career evidence and promotes the strongest fits into your queue.
            </p>
          </div>
          <div className="cx-recommendation-actions">
            <button
              className="ui-button ui-button-ghost"
              type="button"
              disabled={toggleWatch.isPending}
              onClick={() => toggleWatch.mutate()}
            >
              <Radar size={16} />
              {activeWatch?.enabled ? "Pause daily watch" : "Enable daily watch"}
            </button>
            <button
              className="ui-button ui-button-primary"
              type="button"
              disabled={refreshRadar.isPending}
              onClick={() => refreshRadar.mutate()}
            >
              <RefreshCw size={16} />
              {refreshRadar.isPending ? "Judging…" : "Judge fresh jobs"}
            </button>
          </div>
        </div>

        {radar.data ? (
          <div className="cx-recommendation-badges">
            <Badge tone="success">{radar.data.counts.top_match} top matches</Badge>
            <Badge>{radar.data.counts.pending_judgment} waiting for judgment</Badge>
            <span className="cx-confidence">Last {radar.data.lookback_days} days</span>
            {activeWatch ? <Badge tone={activeWatch.enabled ? "success" : "neutral"}>{activeWatch.enabled ? "Daily watch on" : "Daily watch paused"}</Badge> : null}
          </div>
        ) : null}

        {refreshRadar.data ? (
          <div className="cx-trust-note">
            <CheckCircle2 size={16} />
            <span>{refreshRadar.data.scheduled} fresh role{refreshRadar.data.scheduled === 1 ? "" : "s"} scheduled for evidence-based judgment.</span>
          </div>
        ) : null}

        {refreshRadar.isError ? (
          <p className="cx-recommendation-explanation">Radar could not refresh right now. Your existing recommendations are still available below.</p>
        ) : null}

        {radarHistory.data?.items.length ? (
          <div className="cx-trust-note">
            <Radar size={16} />
            <span>
              Latest change: {radarHistory.data.items[0].from_bucket.replaceAll("_", " ")} → {radarHistory.data.items[0].to_bucket.replaceAll("_", " ")}
            </span>
          </div>
        ) : null}

        {radarItems.length ? (
          <div className="cx-recommendation-list">
            {radarItems.map((item) => (
              <Card key={`radar-${item.job_id}`} className="cx-recommendation-card">
                <div className="cx-rank" aria-label="Radar signal"><Radar size={18} /></div>
                <div className="cx-recommendation-main">
                  <div className="cx-recommendation-heading">
                    <div>
                      <p className="cx-action-label">{item.company}</p>
                      <h2>{item.title}</h2>
                    </div>
                    {item.score !== null ? (
                      <div className="cx-match-summary"><strong>{Math.round(item.score)}%</strong><span>match</span></div>
                    ) : null}
                  </div>
                  <div className="cx-recommendation-badges">
                    <Badge tone={item.radar_bucket === "TOP_MATCH" ? "success" : "info"}>
                      {item.radar_bucket === "TOP_MATCH" ? recommendationLabel(item.decision) : "Awaiting judgment"}
                    </Badge>
                    {item.fit_band ? <Badge>{titleCase(item.fit_band)} fit</Badge> : null}
                  </div>
                  <p className="cx-recommendation-explanation">{item.reasons[0]}</p>
                </div>
                <div className="cx-recommendation-actions">
                  <Link className="ui-button ui-button-ghost ui-button-small" href={`/jobs/${item.job_id}`}>Review <ArrowRight size={15} /></Link>
                </div>
              </Card>
            ))}
          </div>
        ) : null}
      </Card>

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
