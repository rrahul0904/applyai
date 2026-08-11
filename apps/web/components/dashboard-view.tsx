"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Bookmark,
  BriefcaseBusiness,
  CheckCircle2,
  Search,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Badge, Card, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/lib/api/client";
import { formatDate, titleCase } from "@/lib/utils";

function matchLabel(decision?: string) {
  if (!decision) return "Worth a look";
  const normalized = decision.toUpperCase();
  if (normalized === "APPLY_NOW") return "Apply now";
  if (normalized === "STRONG") return "Strong fit";
  if (normalized === "CONSIDER") return "Worth considering";
  return titleCase(decision);
}

export function DashboardView() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const me = useQuery({ queryKey: ["me"], queryFn: ({ signal }) => api.auth.me(signal) });
  const jobs = useQuery({
    queryKey: ["jobs", "dashboard"],
    queryFn: ({ signal }) => api.jobs.search(new URLSearchParams({ limit: "6" }), signal),
  });
  const matches = useQuery({
    queryKey: ["career-v2-matches", "dashboard"],
    queryFn: ({ signal }) => api.careerV2.matches(signal),
    retry: false,
  });
  const saved = useQuery({
    queryKey: ["saved-jobs", "dashboard"],
    queryFn: ({ signal }) => api.savedJobs.list(signal),
  });
  const applications = useQuery({
    queryKey: ["applications", "dashboard"],
    queryFn: ({ signal }) => api.applications.list(signal),
  });

  useEffect(() => {
    if (me.data && !me.data.onboarding_completed) router.replace("/onboarding");
  }, [me.data, router]);

  const savedItems = saved.data?.items ?? [];
  const applicationItems = applications.data?.items ?? [];
  const matchByJob = useMemo(
    () => new Map((matches.data?.items ?? []).map((item) => [item.job_id, item])),
    [matches.data?.items],
  );
  const recommendedCount = (matches.data?.items ?? []).filter((item) =>
    ["APPLY_NOW", "STRONG"].includes(item.decision.toUpperCase()),
  ).length;
  const topJob = jobs.data?.items.find((job) => {
    const match = matchByJob.get(job.id);
    return match && ["APPLY_NOW", "STRONG", "CONSIDER"].includes(match.decision.toUpperCase());
  }) ?? jobs.data?.items[0];
  const topMatch = topJob ? matchByJob.get(topJob.id) : undefined;
  const activeApplication = applicationItems.find((item) =>
    !["REJECTED", "WITHDRAWN", "OFFER"].includes(item.current_status.toUpperCase()),
  ) ?? applicationItems[0];

  if (me.isError || jobs.isError || saved.isError || applications.isError) {
    return <ErrorState retry={() => location.reload()} />;
  }

  return (
    <>
      <PageHeader
        eyebrow="Your search"
        title="Your next best moves."
        description="ApplyAI keeps the opportunities, preparation, and follow-ups that matter most in one calm workspace."
        action={<Link className="ui-button ui-button-primary" href="/jobs"><Search size={17} />Explore jobs</Link>}
      />

      <div className="cx-home-metrics" aria-label="Job search overview">
        <div><strong>{matches.isLoading ? "—" : recommendedCount}</strong><span>strong matches</span></div>
        <div><strong>{applicationItems.length}</strong><span>applications</span></div>
        <div><strong>{savedItems.length}</strong><span>saved roles</span></div>
      </div>

      <section className="cx-next-section" aria-labelledby="next-best-moves">
        <div className="cx-section-heading">
          <div>
            <p className="eyebrow">Recommended today</p>
            <h2 id="next-best-moves">Focus on these first</h2>
          </div>
          <Link href="/matches" className="text-button">See recommendations <ArrowRight size={14} /></Link>
        </div>

        <div className="cx-action-grid">
          {jobs.isLoading ? (
            <Card className="cx-action-card cx-action-card-featured">
              <div className="cx-action-icon"><Sparkles size={20} /></div>
              <div className="cx-action-copy">
                <div className="cx-action-kicker"><span>Working on your shortlist</span></div>
                <h3>Finding the opportunities worth your attention.</h3>
                <p>We’re checking fresh roles against your profile and preferences. You can keep using ApplyAI while this finishes.</p>
              </div>
              <Link className="ui-button ui-button-secondary" href="/jobs">Browse all jobs <ArrowRight size={16} /></Link>
            </Card>
          ) : topJob ? (
            <Card className="cx-action-card cx-action-card-featured">
              <div className="cx-action-icon"><Sparkles size={20} /></div>
              <div className="cx-action-copy">
                <div className="cx-action-kicker">
                  <span>Best opportunity to review</span>
                  {topMatch ? <Badge tone="success">{Math.round(topMatch.final_score)}% match</Badge> : <Badge tone="info">Fresh role</Badge>}
                </div>
                <h3>{topJob.title}</h3>
                <p className="cx-action-meta">{topJob.company_name} · {topJob.location ?? "Location flexible"}</p>
                <p>{topMatch ? `${matchLabel(topMatch.decision)} · ${titleCase(topMatch.fit_band)} fit based on your verified profile and preferences.` : "A fresh role from your current job search."}</p>
              </div>
              <Link className="ui-button ui-button-primary" href={`/jobs/${topJob.id}`}>Review & prepare <ArrowRight size={16} /></Link>
            </Card>
          ) : (
            <Card className="cx-action-card cx-action-card-featured">
              <div className="cx-action-icon"><Search size={20} /></div>
              <div className="cx-action-copy"><h3>Find your next opportunity</h3><p>Set your search in motion and ApplyAI will keep the strongest roles easy to find.</p></div>
              <Link className="ui-button ui-button-primary" href="/jobs">Browse jobs</Link>
            </Card>
          )}

          <Card className="cx-action-card">
            <div className="cx-action-icon"><BriefcaseBusiness size={20} /></div>
            <div className="cx-action-copy">
              <span className="cx-action-label">Application momentum</span>
              {activeApplication ? (
                <>
                  <h3>{activeApplication.job.title}</h3>
                  <p className="cx-action-meta">{activeApplication.job.company_name}</p>
                  <p>{titleCase(activeApplication.current_status)} · updated {formatDate(activeApplication.updated_at)}</p>
                </>
              ) : (
                <><h3>No applications yet</h3><p>When a role feels right, start preparation from the job page and keep everything together.</p></>
              )}
            </div>
            <Link className="ui-button ui-button-secondary" href={activeApplication ? `/applications/${activeApplication.id}` : "/jobs"}>{activeApplication ? "Continue" : "Find a role"}<ArrowRight size={16} /></Link>
          </Card>

          <Card className="cx-action-card">
            <div className="cx-action-icon"><Target size={20} /></div>
            <div className="cx-action-copy">
              <span className="cx-action-label">Career Coach</span>
              <h3>Make your evidence work harder</h3>
              <p>Your verified achievements power matching, resume tailoring, and interview preparation without inventing experience.</p>
            </div>
            <Link className="ui-button ui-button-secondary" href="/career">Open Career Coach <ArrowRight size={16} /></Link>
          </Card>
        </div>
      </section>

      <section className="cx-home-lower" aria-label="More opportunities and saved work">
        <Card className="cx-home-panel">
          <div className="cx-section-heading compact">
            <div><p className="eyebrow">More opportunities</p><h2>Fresh roles</h2></div>
            <Link href="/jobs" className="text-button">View all <ArrowRight size={14} /></Link>
          </div>
          <div className="cx-clean-list">
            {(jobs.data?.items ?? []).slice(0, 4).map((job) => {
              const career = matchByJob.get(job.id);
              return (
                <Link href={`/jobs/${job.id}`} className="cx-clean-row" key={job.id}>
                  <div className="cx-company-avatar" aria-hidden="true">{job.company_name.charAt(0)}</div>
                  <div><strong>{job.title}</strong><span>{job.company_name} · {job.location ?? "Location flexible"}</span></div>
                  {career ? <Badge tone="success">{Math.round(career.final_score)}%</Badge> : null}
                  <ArrowRight size={17} />
                </Link>
              );
            })}
          </div>
        </Card>

        <Card className="cx-home-panel">
          <div className="cx-section-heading compact">
            <div><p className="eyebrow">Saved for later</p><h2>Your shortlist</h2></div>
            <Link href="/saved" className="text-button">See saved</Link>
          </div>
          {savedItems.length ? (
            <div className="cx-shortlist">
              {savedItems.slice(0, 4).map((job) => (
                <Link href={`/jobs/${job.id}`} key={job.id}>
                  <Bookmark size={16} />
                  <span><strong>{job.title}</strong><small>{job.company_name}</small></span>
                </Link>
              ))}
            </div>
          ) : (
            <div className="cx-gentle-empty">
              <CheckCircle2 size={20} />
              <p>Save roles you want to compare later. Your shortlist will stay here without cluttering today’s priorities.</p>
            </div>
          )}
        </Card>
      </section>

      <Card className="cx-search-strip">
        <div><strong>Looking for something specific?</strong><span>Search by title, skill, or company.</span></div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            router.push(query ? `/jobs?keyword=${encodeURIComponent(query)}` : "/jobs");
          }}
        >
          <input className="ui-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. Data Engineering Manager" aria-label="Search jobs" />
          <button className="ui-button ui-button-primary" type="submit"><Search size={17} />Search</button>
        </form>
      </Card>
    </>
  );
}
