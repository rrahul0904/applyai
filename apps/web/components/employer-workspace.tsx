"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, Building2, Plus, UsersRound } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { platformApi } from "@/lib/api/platform-client";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, NativeSelect, PageHeader, Skeleton, Textarea } from "@/components/ui";

export function EmployerWorkspace() {
  const queryClient = useQueryClient();
  const organizations = useQuery({ queryKey: ["employer-organizations"], queryFn: platformApi.employer.organizations });
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
  const org = useMemo(() => {
    const rows = organizations.data ?? [];
    return rows.find((item) => String(item.id) === selectedOrgId) ?? rows[0] ?? null;
  }, [organizations.data, selectedOrgId]);
  const orgId = org ? String(org.id) : null;
  const dashboard = useQuery({ queryKey: ["employer-dashboard", orgId], queryFn: () => platformApi.employer.dashboard(orgId!), enabled: Boolean(orgId) });
  const jobs = useQuery({ queryKey: ["employer-jobs", orgId], queryFn: () => platformApi.employer.jobs(orgId!), enabled: Boolean(orgId) });
  const [orgName, setOrgName] = useState("");
  const createOrg = useMutation({ mutationFn: () => platformApi.employer.createOrganization(orgName), onSuccess: async (created) => { setOrgName(""); setSelectedOrgId(String(created.id)); await queryClient.invalidateQueries({ queryKey: ["employer-organizations"] }); toast.success("Employer organization created"); } });
  const [title, setTitle] = useState(""); const [description, setDescription] = useState(""); const [location, setLocation] = useState(""); const [workMode, setWorkMode] = useState("HYBRID");
  const createJob = useMutation({ mutationFn: () => platformApi.employer.createJob(orgId!, { title, description, location_text: location || null, work_mode: workMode, employment_type: "FULL_TIME", currency: "USD" }), onSuccess: async () => { setTitle(""); setDescription(""); setLocation(""); await queryClient.invalidateQueries({ queryKey: ["employer-jobs", orgId] }); toast.success("Job draft created"); } });
  const publish = useMutation({ mutationFn: platformApi.employer.publishJob, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["employer-jobs", orgId] }); await queryClient.invalidateQueries({ queryKey: ["employer-dashboard", orgId] }); toast.success("Job published to the candidate marketplace"); }, onError: (error) => toast.error(error.message) });
  const close = useMutation({ mutationFn: platformApi.employer.closeJob, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["employer-jobs", orgId] }); queryClient.invalidateQueries({ queryKey: ["employer-dashboard", orgId] }); } });
  const [applicantJobId, setApplicantJobId] = useState<string | null>(null);
  const applicants = useQuery({ queryKey: ["employer-applicants", applicantJobId], queryFn: () => platformApi.employer.applicants(applicantJobId!), enabled: Boolean(applicantJobId) });

  if (organizations.isLoading) return <Skeleton className="page-skeleton" />;
  if (organizations.isError) return <ErrorState message={organizations.error.message} retry={() => organizations.refetch()} />;

  return <>
    <PageHeader eyebrow="Recruiting platform" title="Employer Workspace" description="Create verified organizations, publish first-party jobs into ApplyAI search, and manage candidates who submit through ApplyAI." />
    {!org ? <Card className="detail-section"><EmptyState icon={<Building2/>} title="Create an employer organization" description="An organization is the verified boundary for recruiters, jobs and applicants."/><form className="form-stack" onSubmit={(event) => { event.preventDefault(); if (orgName.trim()) createOrg.mutate(); }}><Field label="Organization name" htmlFor="org-name"><Input id="org-name" value={orgName} onChange={(e) => setOrgName(e.target.value)} /></Field><Button type="submit" disabled={!orgName.trim()}><Plus size={16}/>Create organization</Button></form></Card> : <>
      <Card className="detail-section"><div className="section-header"><div><h2>{String(org.name)}</h2><p>Organization workspace</p></div><Badge tone={String(org.verification_status) === "VERIFIED" ? "success" : "warning"}>{String(org.verification_status)}</Badge></div>{(organizations.data ?? []).length > 1 ? <NativeSelect value={String(org.id)} onChange={(e) => setSelectedOrgId(e.target.value)}>{(organizations.data ?? []).map((item) => <option value={String(item.id)} key={String(item.id)}>{String(item.name)}</option>)}</NativeSelect> : null}</Card>
      <div className="dashboard-grid"><Card><p className="eyebrow">Jobs</p><h2>{JSON.stringify(dashboard.data?.jobs ?? {})}</h2></Card><Card><p className="eyebrow">Applicants</p><h2>{String(dashboard.data?.applicant_count ?? 0)}</h2></Card><Card><p className="eyebrow">Pipeline</p><h2>{Object.keys((dashboard.data?.applicants_by_stage as object | undefined) ?? {}).length} stages</h2></Card></div>
      <Card id="jobs" className="detail-section"><div className="section-header"><div><h2>Post a job</h2><p>Published roles become first-party canonical jobs in candidate search.</p></div><BriefcaseBusiness/></div><form className="form-stack" onSubmit={(event) => { event.preventDefault(); if (title.trim() && description.trim().length >= 20) createJob.mutate(); }}><Field label="Title" htmlFor="job-title"><Input id="job-title" value={title} onChange={(e) => setTitle(e.target.value)} /></Field><Field label="Description" htmlFor="job-description"><Textarea id="job-description" rows={8} value={description} onChange={(e) => setDescription(e.target.value)} /></Field><div className="form-grid"><Field label="Location" htmlFor="job-location"><Input id="job-location" value={location} onChange={(e) => setLocation(e.target.value)} /></Field><Field label="Work mode" htmlFor="job-mode"><NativeSelect id="job-mode" value={workMode} onChange={(e) => setWorkMode(e.target.value)}><option>REMOTE</option><option>HYBRID</option><option>ONSITE</option></NativeSelect></Field></div><Button type="submit" disabled={!title.trim() || description.trim().length < 20}>Create draft</Button></form></Card>
      <div className="list-stack">{(jobs.data ?? []).map((job) => <Card className="detail-section" key={String(job.id)}><div className="section-header"><div><h2>{String(job.title)}</h2><p>{String(job.location_text ?? "Flexible location")}</p></div><Badge tone={String(job.status) === "PUBLISHED" ? "success" : String(job.status) === "CLOSED" ? "neutral" : "info"}>{String(job.status)}</Badge></div><div className="button-row">{String(job.status) !== "PUBLISHED" && String(job.status) !== "CLOSED" ? <Button size="small" onClick={() => publish.mutate(String(job.id))}>Publish</Button> : null}{String(job.status) === "PUBLISHED" ? <><Button variant="secondary" size="small" onClick={() => setApplicantJobId(String(job.id))}><UsersRound size={15}/>Applicants</Button><Button variant="ghost" size="small" onClick={() => close.mutate(String(job.id))}>Close</Button></> : null}</div></Card>)}</div>
      {applicantJobId ? <Card id="applicants" className="detail-section"><div className="section-header"><div><h2>Applicant pipeline</h2><p>First-party ApplyAI submissions appear here immediately.</p></div><UsersRound/></div><div className="list-stack">{(applicants.data ?? []).map((row) => <div className="note" key={String(row.id)}><strong>{String(row.candidate_email)}</strong><span>{String(row.stage)} · {String(row.application_status)}</span></div>)}{!applicants.data?.length ? <p className="muted">No applicants yet.</p> : null}</div></Card> : null}
    </>}
  </>;
}
