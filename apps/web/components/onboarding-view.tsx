"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Profile, type ProfileWrite } from "@/lib/api/client";
import { Button, ErrorState, Field, Input, Progress, Textarea } from "@/components/ui";

const stages = [
  "ACCOUNT_CREATED",
  "RESUME",
  "RESUME_PROCESSING",
  "PROFILE_REVIEW",
  "TARGET_ROLES",
  "LOCATION",
  "WORK_PREFERENCES",
  "COMPENSATION",
  "REVIEW",
  "COMPLETE",
] as const;

type Stage = (typeof stages)[number];
type ExperienceDraft = { company_name: string; title: string; description: string };
type EducationDraft = { institution: string; degree: string; field_of_study: string };
type Draft = {
  headline: string;
  current_title: string;
  summary: string;
  years_experience: string;
  target_roles: string[];
  location_text: string;
  work_modes: string[];
  minimum_compensation: string;
  experiences: ExperienceDraft[];
  education: EducationDraft[];
  skills: string[];
};

const emptyDraft: Draft = {
  headline: "",
  current_title: "",
  summary: "",
  years_experience: "",
  target_roles: [],
  location_text: "",
  work_modes: [],
  minimum_compensation: "",
  experiences: [],
  education: [],
  skills: [],
};

function fromProfile(profile: Profile | null | undefined): Draft {
  if (!profile) return emptyDraft;
  return {
    headline: profile.headline ?? "",
    current_title: profile.current_title ?? "",
    summary: profile.summary ?? "",
    years_experience: profile.years_experience == null ? "" : String(profile.years_experience),
    target_roles: profile.target_roles ?? [],
    location_text: profile.location_text ?? "",
    work_modes: profile.work_modes ?? [],
    minimum_compensation:
      profile.minimum_compensation == null ? "" : String(profile.minimum_compensation),
    experiences: (profile.experiences ?? []).map((item) => ({
      company_name: item.company_name,
      title: item.title,
      description: item.description ?? "",
    })),
    education: (profile.education ?? []).map((item) => ({
      institution: item.institution,
      degree: item.degree ?? "",
      field_of_study: item.field_of_study ?? "",
    })),
    skills: (profile.skills ?? []).map((item) => item.name),
  };
}

function toPayload(draft: Draft): ProfileWrite {
  return {
    headline: draft.headline || null,
    current_title: draft.current_title || null,
    summary: draft.summary || null,
    years_experience: draft.years_experience ? Number(draft.years_experience) : null,
    target_roles: draft.target_roles.filter(Boolean),
    location_text: draft.location_text || null,
    work_modes: draft.work_modes,
    minimum_compensation: draft.minimum_compensation
      ? Number(draft.minimum_compensation)
      : null,
    experiences: draft.experiences
      .filter((item) => item.company_name.trim() && item.title.trim())
      .map((item) => ({ ...item, provenance: "USER_ENTERED" })),
    education: draft.education
      .filter((item) => item.institution.trim())
      .map((item) => ({ ...item, provenance: "USER_ENTERED" })),
    skills: draft.skills
      .filter((name) => name.trim())
      .map((name) => ({ name: name.trim(), provenance: "USER_ENTERED" })),
  };
}

function extractedDraft(structuredData: Record<string, unknown> | null, current: Draft): Draft {
  if (!structuredData) return current;
  const basic = (structuredData.basic_profile ?? {}) as Record<string, unknown>;
  const experiences = Array.isArray(structuredData.experiences)
    ? structuredData.experiences as Array<Record<string, unknown>>
    : [];
  const education = Array.isArray(structuredData.education)
    ? structuredData.education as Array<Record<string, unknown>>
    : [];
  const skills = Array.isArray(structuredData.skills)
    ? structuredData.skills as Array<Record<string, unknown>>
    : [];
  return {
    ...current,
    current_title: String(basic.current_title ?? current.current_title ?? ""),
    experiences: experiences.map((item) => ({
      company_name: String(item.company_name ?? ""),
      title: String(item.title ?? ""),
      description: String(item.description ?? ""),
    })),
    education: education.map((item) => ({
      institution: String(item.institution ?? ""),
      degree: String(item.degree ?? ""),
      field_of_study: String(item.field_of_study ?? ""),
    })),
    skills: skills.map((item) => String(item.name ?? "")).filter(Boolean),
  };
}

export function OnboardingView() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const onboarding = useQuery({
    queryKey: ["onboarding"],
    queryFn: ({ signal }) => api.onboarding.get(signal),
  });
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: ({ signal }) => api.profile.get(signal),
  });
  const resumes = useQuery({
    queryKey: ["resumes"],
    queryFn: ({ signal }) => api.resumes.list(signal),
    refetchInterval: 1500,
  });
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [draftReady, setDraftReady] = useState(false);
  const [roleInput, setRoleInput] = useState("");
  const [skillInput, setSkillInput] = useState("");

  useEffect(() => {
    if (!draftReady && profile.data !== undefined) {
      setDraft(fromProfile(profile.data));
      setDraftReady(true);
    }
  }, [draftReady, profile.data]);

  useEffect(() => {
    if (onboarding.data?.onboarding_completed) router.replace("/dashboard");
  }, [onboarding.data, router]);

  const stage = (onboarding.data?.onboarding_stage ?? "ACCOUNT_CREATED") as Stage;
  const stageIndex = Math.max(0, stages.indexOf(stage));
  const progress = Math.round((stageIndex / (stages.length - 1)) * 100);
  const latestResume = resumes.data?.[0];
  const extraction = useQuery({
    queryKey: ["resume-extraction", latestResume?.resume_id],
    queryFn: ({ signal }) => api.resumes.extraction(latestResume!.resume_id, signal),
    enabled: Boolean(
      latestResume
      && ["NEEDS_REVIEW", "FAILED", "COMPLETED"].includes(latestResume.processing_status),
    ),
    retry: false,
  });

  useEffect(() => {
    if (
      ["RESUME_PROCESSING", "PROFILE_REVIEW"].includes(stage)
      && latestResume?.processing_status === "NEEDS_REVIEW"
      && extraction.data
    ) {
      setDraft((current) => extractedDraft(
        extraction.data.structured_data as Record<string, unknown> | null,
        current,
      ));
    }
  }, [stage, latestResume?.processing_status, extraction.data]);

  const stageMutation = useMutation({
    mutationFn: (next: string) => api.onboarding.update(next),
    onSuccess: (data) => queryClient.setQueryData(["onboarding"], data),
  });
  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = toPayload(draft);
      const shouldConfirmResume = stage === "PROFILE_REVIEW"
        && latestResume?.processing_status === "NEEDS_REVIEW"
        && extraction.data?.status === "NEEDS_REVIEW";
      if (shouldConfirmResume) {
        return api.resumes.confirm(latestResume.resume_id, payload);
      }
      return api.profile.save(payload);
    },
    onSuccess: async (data) => {
      queryClient.setQueryData(["profile"], data);
      await queryClient.invalidateQueries({ queryKey: ["resumes"] });
      await queryClient.invalidateQueries({ queryKey: ["resume-extraction"] });
    },
  });
  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.resumes.upload(file),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["resumes"] });
      await stageMutation.mutateAsync("RESUME_PROCESSING");
    },
  });

  const busy = stageMutation.isPending || saveMutation.isPending || uploadMutation.isPending;
  const error = stageMutation.error || saveMutation.error || uploadMutation.error;
  const canComplete = Boolean(
    (draft.current_title || draft.headline) && draft.target_roles.length && draft.work_modes.length,
  );

  const shell = (content: React.ReactNode) => (
    <main className="onboarding-main">
      <div className="onboarding-progress">
        <div className="onboarding-progress-label">
          <span>Candidate setup</span>
          <span>{progress}% complete</span>
        </div>
        <Progress value={progress} />
      </div>
      <section className="onboarding-card">
        {error ? <ErrorState message={error.message} /> : content}
      </section>
    </main>
  );

  if (onboarding.isLoading || profile.isLoading || !draftReady) {
    return shell(<><p className="eyebrow">ApplyAI setup</p><h1>Loading your candidate profile…</h1><p>Your progress is saved to your account.</p></>);
  }
  if (onboarding.isError || profile.isError) {
    return shell(<ErrorState message="We couldn't load your onboarding state." retry={() => location.reload()} />);
  }

  if (stage === "ACCOUNT_CREATED") {
    return shell(<>
      <p className="eyebrow">Welcome to ApplyAI</p>
      <h1>Build a search workspace that remembers your progress.</h1>
      <p>We’ll create your candidate profile, preferences, and resume foundation before job discovery.</p>
      <Button onClick={() => stageMutation.mutate("RESUME")} disabled={busy}>Start setup</Button>
    </>);
  }

  if (stage === "RESUME") {
    return shell(<>
      <p className="eyebrow">Resume</p>
      <h1>Start from your resume, or enter details manually.</h1>
      <p>PDF and DOCX files are stored privately. Parser output stays reviewable until you confirm it.</p>
      <label className="dropzone">
        <Upload size={32} aria-hidden="true" />
        <strong>Upload a PDF or DOCX</strong>
        <p>Maximum file size: 5 MB.</p>
        <input
          className="sr-only"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) uploadMutation.mutate(file);
          }}
        />
        <span className="ui-button ui-button-primary ui-button-small">Choose file</span>
      </label>
      <div className="button-row" style={{ marginTop: 18 }}>
        <Button variant="ghost" onClick={() => stageMutation.mutate("PROFILE_REVIEW")} disabled={busy}>Continue without a resume</Button>
      </div>
    </>);
  }

  if (stage === "RESUME_PROCESSING") {
    const status = latestResume?.processing_status ?? "QUEUED";
    return shell(<>
      <p className="eyebrow">Resume processing</p>
      <h1>{status === "FAILED" ? "We couldn’t fully read this resume." : "We’re extracting your experience and skills."}</h1>
      <p>{status === "FAILED" ? "You can continue manually or go back and upload another version." : "This step is deterministic and reviewable. Nothing extracted becomes candidate truth until you confirm it."}</p>
      {latestResume ? <div className="upload-file"><FileText size={22} /><div><strong>{latestResume.filename}</strong><span>{status.replaceAll("_", " ")}</span></div></div> : null}
      <div className="button-row">
        {status === "NEEDS_REVIEW" ? <Button onClick={() => stageMutation.mutate("PROFILE_REVIEW")}>Review extracted profile</Button> : null}
        {status === "FAILED" ? <Button onClick={() => stageMutation.mutate("PROFILE_REVIEW")}>Enter information manually</Button> : null}
        <Button variant="ghost" onClick={() => stageMutation.mutate("RESUME")}>Upload another file</Button>
      </div>
    </>);
  }

  if (stage === "PROFILE_REVIEW") {
    return shell(<>
      <p className="eyebrow">Profile review</p>
      <h1>Review what employers should know about you.</h1>
      <p>Correct parser output before it becomes your canonical candidate profile.</p>
      <div className="form-stack">
        <div className="form-grid">
          <Field label="Current title" htmlFor="current-title"><Input id="current-title" value={draft.current_title} onChange={(e) => setDraft({ ...draft, current_title: e.target.value })} /></Field>
          <Field label="Years of experience" htmlFor="years"><Input id="years" type="number" min="0" max="80" value={draft.years_experience} onChange={(e) => setDraft({ ...draft, years_experience: e.target.value })} /></Field>
          <Field className="full-width" label="Headline" htmlFor="headline"><Input id="headline" value={draft.headline} onChange={(e) => setDraft({ ...draft, headline: e.target.value })} /></Field>
          <Field className="full-width" label="Professional summary" htmlFor="summary"><Textarea id="summary" value={draft.summary} onChange={(e) => setDraft({ ...draft, summary: e.target.value })} /></Field>
        </div>
        <h2>Experience</h2>
        {draft.experiences.map((item, index) => <div className="repeater-item form-grid" key={`experience-${index}`}>
          <Field label="Company" htmlFor={`company-${index}`}><Input id={`company-${index}`} value={item.company_name} onChange={(e) => setDraft({ ...draft, experiences: draft.experiences.map((x, i) => i === index ? { ...x, company_name: e.target.value } : x) })} /></Field>
          <Field label="Title" htmlFor={`title-${index}`}><Input id={`title-${index}`} value={item.title} onChange={(e) => setDraft({ ...draft, experiences: draft.experiences.map((x, i) => i === index ? { ...x, title: e.target.value } : x) })} /></Field>
          <Field className="full-width" label="Description" htmlFor={`description-${index}`}><Textarea id={`description-${index}`} value={item.description} onChange={(e) => setDraft({ ...draft, experiences: draft.experiences.map((x, i) => i === index ? { ...x, description: e.target.value } : x) })} /></Field>
          <Button className="remove-item" size="small" variant="ghost" type="button" onClick={() => setDraft({ ...draft, experiences: draft.experiences.filter((_, i) => i !== index) })}>Remove</Button>
        </div>)}
        <Button variant="secondary" type="button" onClick={() => setDraft({ ...draft, experiences: [...draft.experiences, { company_name: "", title: "", description: "" }] })}>Add experience</Button>
        <h2>Education</h2>
        {draft.education.map((item, index) => <div className="repeater-item form-grid" key={`education-${index}`}>
          <Field className="full-width" label="Institution" htmlFor={`institution-${index}`}><Input id={`institution-${index}`} value={item.institution} onChange={(e) => setDraft({ ...draft, education: draft.education.map((x, i) => i === index ? { ...x, institution: e.target.value } : x) })} /></Field>
          <Field label="Degree" htmlFor={`degree-${index}`}><Input id={`degree-${index}`} value={item.degree} onChange={(e) => setDraft({ ...draft, education: draft.education.map((x, i) => i === index ? { ...x, degree: e.target.value } : x) })} /></Field>
          <Field label="Field of study" htmlFor={`field-${index}`}><Input id={`field-${index}`} value={item.field_of_study} onChange={(e) => setDraft({ ...draft, education: draft.education.map((x, i) => i === index ? { ...x, field_of_study: e.target.value } : x) })} /></Field>
          <Button className="remove-item" size="small" variant="ghost" type="button" onClick={() => setDraft({ ...draft, education: draft.education.filter((_, i) => i !== index) })}>Remove</Button>
        </div>)}
        <Button variant="secondary" type="button" onClick={() => setDraft({ ...draft, education: [...draft.education, { institution: "", degree: "", field_of_study: "" }] })}>Add education</Button>
        <h2>Skills</h2>
        <div className="button-row"><Input aria-label="Add skill" value={skillInput} onChange={(e) => setSkillInput(e.target.value)} placeholder="Python, SQL, AWS…" /><Button type="button" variant="secondary" onClick={() => { if (skillInput.trim()) setDraft({ ...draft, skills: [...new Set([...draft.skills, skillInput.trim()])] }); setSkillInput(""); }}>Add skill</Button></div>
        <div className="chips">{draft.skills.map((skill) => <button className="ui-badge" type="button" key={skill} onClick={() => setDraft({ ...draft, skills: draft.skills.filter((item) => item !== skill) })}>{skill} ×</button>)}</div>
        <Button onClick={async () => { await saveMutation.mutateAsync(); await stageMutation.mutateAsync("TARGET_ROLES"); }} disabled={busy || !(draft.current_title || draft.headline)}>Save and continue</Button>
      </div>
    </>);
  }

  if (stage === "TARGET_ROLES") {
    return shell(<>
      <p className="eyebrow">Target roles</p><h1>What roles are you pursuing?</h1><p>Your first role is treated as the primary target.</p>
      <div className="form-stack">
        <div className="button-row"><Input aria-label="Target role" value={roleInput} onChange={(e) => setRoleInput(e.target.value)} placeholder="Staff Data Engineer" /><Button type="button" variant="secondary" onClick={() => { if (roleInput.trim()) setDraft({ ...draft, target_roles: [...new Set([...draft.target_roles, roleInput.trim()])] }); setRoleInput(""); }}>Add role</Button></div>
        <div className="chips">{draft.target_roles.map((role, index) => <button className="ui-badge" type="button" key={role} onClick={() => setDraft({ ...draft, target_roles: draft.target_roles.filter((item) => item !== role) })}>{index === 0 ? "Primary · " : ""}{role} ×</button>)}</div>
        <Button disabled={busy || !draft.target_roles.length} onClick={async () => { await saveMutation.mutateAsync(); await stageMutation.mutateAsync("LOCATION"); }}>Save and continue</Button>
      </div>
    </>);
  }

  if (stage === "LOCATION") {
    return shell(<>
      <p className="eyebrow">Location</p><h1>Where do you want to work?</h1><p>Use a city, region, country, or “United States” for a broad search preference.</p>
      <Field label="Preferred location" htmlFor="preferred-location"><Input id="preferred-location" value={draft.location_text} onChange={(e) => setDraft({ ...draft, location_text: e.target.value })} placeholder="Boston, MA" /></Field>
      <div className="button-row" style={{ marginTop: 18 }}><Button onClick={async () => { await saveMutation.mutateAsync(); await stageMutation.mutateAsync("WORK_PREFERENCES"); }}>Save and continue</Button></div>
    </>);
  }

  if (stage === "WORK_PREFERENCES") {
    return shell(<>
      <p className="eyebrow">Work preferences</p><h1>Choose the arrangements that work for you.</h1><p>Select one or more. These preferences will later feed hard eligibility filters before matching.</p>
      <div className="choice-grid">{["REMOTE", "HYBRID", "ONSITE"].map((mode) => <label className="choice" key={mode}><input type="checkbox" checked={draft.work_modes.includes(mode)} onChange={(e) => setDraft({ ...draft, work_modes: e.target.checked ? [...draft.work_modes, mode] : draft.work_modes.filter((item) => item !== mode) })} />{mode === "ONSITE" ? "On-site" : mode.charAt(0) + mode.slice(1).toLowerCase()}</label>)}</div>
      <div className="button-row" style={{ marginTop: 18 }}><Button disabled={!draft.work_modes.length} onClick={async () => { await saveMutation.mutateAsync(); await stageMutation.mutateAsync("COMPENSATION"); }}>Save and continue</Button></div>
    </>);
  }

  if (stage === "COMPENSATION") {
    return shell(<>
      <p className="eyebrow">Compensation</p><h1>Set an optional minimum salary.</h1><p>You can skip this. It stays private and is used only for your job preferences.</p>
      <Field label="Minimum annual compensation (USD)" htmlFor="minimum-comp"><Input id="minimum-comp" type="number" min="0" step="5000" value={draft.minimum_compensation} onChange={(e) => setDraft({ ...draft, minimum_compensation: e.target.value })} placeholder="150000" /></Field>
      <div className="button-row" style={{ marginTop: 18 }}><Button onClick={async () => { await saveMutation.mutateAsync(); await stageMutation.mutateAsync("REVIEW"); }}>Continue</Button></div>
    </>);
  }

  if (stage === "REVIEW") {
    return shell(<>
      <p className="eyebrow">Review</p><h1>Your candidate workspace is ready.</h1><p>Confirm the minimum profile information below. You can edit everything later from Profile.</p>
      <div className="completion-summary">
        <div className="summary-row"><span>Professional identity</span><strong>{draft.current_title || draft.headline || "Missing"}</strong></div>
        <div className="summary-row"><span>Primary target</span><strong>{draft.target_roles[0] ?? "Missing"}</strong></div>
        <div className="summary-row"><span>Location</span><strong>{draft.location_text || "Flexible"}</strong></div>
        <div className="summary-row"><span>Work modes</span><strong>{draft.work_modes.join(", ") || "Missing"}</strong></div>
        <div className="summary-row"><span>Skills</span><strong>{draft.skills.length} saved</strong></div>
      </div>
      <Button disabled={!canComplete || busy} onClick={async () => { await saveMutation.mutateAsync(); await stageMutation.mutateAsync("COMPLETE"); router.push("/dashboard"); }}><CheckCircle2 size={18} />Complete onboarding</Button>
    </>);
  }

  return shell(<><p className="eyebrow">Complete</p><h1>Taking you to your dashboard…</h1></>);
}
