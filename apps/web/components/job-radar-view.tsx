"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle, ExternalLink, Radio, RotateCw } from "lucide-react";
import { Button, EmptyState, ErrorState, Field, Input, NativeSelect, PageHeader, Skeleton } from "@/components/ui";
import { platformApi, PlatformApiError, type JobRadarProfile, type JobRadarScan } from "@/lib/api/platform-client";

const emptyProfile: Omit<JobRadarProfile, "id"> = {
  target_titles: [""], skills: [], years_experience: null, seniority_preferences: [],
  preferred_locations: [], remote_policy: "ANY", salary_min: null, salary_currency: "USD",
};

function list(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function ScanResults({ scan }: { scan: JobRadarScan }) {
  return <section className="detail-section" aria-live="polite">
    <h2>Latest scan</h2>
    <p>State: <strong>{scan.status}</strong>. {scan.jobs_ranked} ranked from {scan.jobs_seen} seen.</p>
    {scan.error_detail && <p role="alert">{scan.error_code ?? "SCAN_ERROR"}: {scan.error_detail}</p>}
    {scan.status === "QUEUED" || scan.status === "RUNNING" ? <p>The scan is still running. This view refreshes every few seconds.</p> : null}
    {scan.status === "COMPLETED" && scan.matches.length === 0 ? <EmptyState title="No matching jobs in this scan" description="Try another target title, skill, or location, then run a new scan." /> : null}
    <div className="list-stack">{scan.matches.map((match) => <article className="detail-section" key={match.id}>
      <div className="section-header"><div><p className="eyebrow">Rank {match.rank}</p><h3>{String(match.source_evidence.title ?? "Job opportunity")}</h3><p>{String(match.source_evidence.company ?? "Company details unavailable")}</p></div><strong>{Math.round(match.deterministic_score)} score</strong></div>
      <p>{String(match.source_evidence.explanation ?? "Ranked by deterministic title, skills, experience, location and salary fit.")}</p>
      <p>Remote eligibility: {String((match.source_evidence.remote_eligibility as Record<string, unknown> | undefined)?.decision ?? "UNKNOWN")}</p>
      <a href={match.application_url} target="_blank" rel="noreferrer">View posting <ExternalLink size={14} aria-hidden="true" /></a>
    </article>)}</div>
    <p className="muted-copy">This scan uses the canonical ApplyAI job store. External provider search, AI reranking, streaming and scheduled delivery are not enabled.</p>
  </section>;
}

export function JobRadarView() {
  const queryClient = useQueryClient();
  const profileQuery = useQuery({ queryKey: ["job-radar-profile"], queryFn: platformApi.jobRadar.profile, retry: (count, error) => !(error instanceof PlatformApiError && error.status === 404) && count < 2 });
  const [draft, setDraft] = useState<Partial<Omit<JobRadarProfile, "id">>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const profile: Omit<JobRadarProfile, "id"> = { ...(profileQuery.data ?? emptyProfile), ...draft };
  const save = useMutation({ mutationFn: platformApi.jobRadar.saveProfile, onSuccess: (data) => { queryClient.setQueryData(["job-radar-profile"], data); setDraft({}); setFormError(null); } });
  const scan = useMutation({ mutationFn: platformApi.jobRadar.createScan });
  const scanQuery = useQuery({ queryKey: ["job-radar-scan", scan.data?.id], queryFn: () => platformApi.jobRadar.getScan(scan.data!.id), enabled: Boolean(scan.data?.id) && ["QUEUED", "RUNNING"].includes(scan.data?.status ?? ""), refetchInterval: (query) => ["QUEUED", "RUNNING"].includes(query.state.data?.status ?? scan.data?.status ?? "") ? 2500 : false });
  const latestScan = scanQuery.data ?? scan.data ?? null;
  const update = (key: keyof typeof emptyProfile, value: string) => setDraft((current) => ({ ...current, [key]: value }));
  const saveProfile = () => {
    const titles = list(profile.target_titles.join(","));
    if (titles.length === 0) { setFormError("Add at least one target role."); return; }
    save.mutate({ ...profile, target_titles: titles, skills: list(profile.skills.join(",")), seniority_preferences: list(profile.seniority_preferences.join(",")), preferred_locations: list(profile.preferred_locations.join(",")) });
  };
  const profileMissing = profileQuery.error instanceof PlatformApiError && profileQuery.error.status === 404;
  if (profileQuery.isPending) return <main className="page-content"><Skeleton className="page-skeleton" /></main>;
  if (profileQuery.isError && !profileMissing) return <main className="page-content"><ErrorState title="Job Radar is unavailable" message={profileQuery.error.message} retry={() => void profileQuery.refetch()} /></main>;
  return <main className="page-content">
    <PageHeader eyebrow="JOB DISCOVERY" title="Job Radar" description="Save the roles, skills and locations you want to target, then scan ApplyAI’s canonical job inventory." />
    <section className="detail-section" aria-labelledby="radar-profile-title">
      <h2 id="radar-profile-title">Search profile</h2>
      {profileMissing && <p>Set up a profile before your first scan. Your saved candidate profile is not changed by these preferences.</p>}
      <div className="form-grid">
        <Field label="Target roles (comma separated)" htmlFor="radar-titles"><Input id="radar-titles" value={profile.target_titles.join(", ")} onChange={(event) => update("target_titles", event.target.value)} placeholder="Product manager, Data analyst" /></Field>
        <Field label="Skills (comma separated)" htmlFor="radar-skills"><Input id="radar-skills" value={profile.skills.join(", ")} onChange={(event) => update("skills", event.target.value)} placeholder="SQL, Python, product strategy" /></Field>
        <Field label="Preferred locations (comma separated)" htmlFor="radar-locations"><Input id="radar-locations" value={profile.preferred_locations.join(", ")} onChange={(event) => update("preferred_locations", event.target.value)} placeholder="New York, United States" /></Field>
        <Field label="Work arrangement" htmlFor="radar-work-mode"><NativeSelect id="radar-work-mode" value={profile.remote_policy} onChange={(event) => update("remote_policy", event.target.value)}><option value="ANY">Any</option><option value="REMOTE">Remote</option><option value="HYBRID">Hybrid</option><option value="ONSITE">On-site</option></NativeSelect></Field>
        <Field label="Years of experience" htmlFor="radar-years"><Input id="radar-years" type="number" min="0" max="80" value={profile.years_experience ?? ""} onChange={(event) => setDraft((current) => ({ ...current, years_experience: event.target.value ? Number(event.target.value) : null }))} /></Field>
        <Field label="Minimum annual salary" htmlFor="radar-salary"><Input id="radar-salary" type="number" min="0" value={profile.salary_min ?? ""} onChange={(event) => setDraft((current) => ({ ...current, salary_min: event.target.value ? Number(event.target.value) : null }))} /></Field>
      </div>
      {formError && <p role="alert">{formError}</p>}
      {save.isError && <p role="alert">Could not save the search profile: {save.error.message}</p>}
      <Button disabled={save.isPending} onClick={saveProfile}>{save.isPending ? "Saving…" : "Save search profile"}</Button>
      {save.isSuccess && <p role="status">Search profile saved.</p>}
    </section>
    <section className="detail-section"><h2>Run a scan</h2><p>Scans are durable and safe to retry. Results explain how each job ranked.</p>
      {scan.isError && <p role="alert">{scan.error.message}. Save the profile and retry when the scan service is available.</p>}
      <Button disabled={!profileQuery.data || save.isPending || scan.isPending} onClick={() => scan.mutate()}><Radio size={16} />{scan.isPending ? "Starting scan…" : "Scan jobs"}</Button>
      {latestScan && <Button variant="secondary" disabled={scan.isPending} onClick={() => scan.mutate()}><RotateCw size={15} />New scan</Button>}
    </section>
    {scanQuery.isError && <p role="alert"><AlertTriangle size={16} /> Latest scan status could not be refreshed. Retry the status request.</p>}
    {latestScan && <ScanResults scan={latestScan} />}
  </main>;
}
