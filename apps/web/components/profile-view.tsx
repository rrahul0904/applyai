"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, type Profile, type ProfileWrite } from "@/lib/api/client";
import { Badge, Button, Card, ErrorState, Field, Input, PageHeader, Skeleton, Textarea } from "@/components/ui";

const emptyProfile: ProfileWrite = {
  headline: null,
  current_title: null,
  summary: null,
  years_experience: null,
  target_roles: [],
  location_text: null,
  work_modes: [],
  minimum_compensation: null,
  experiences: [],
  education: [],
  skills: [],
};

function toProfileWrite(profile: Profile | null | undefined): ProfileWrite {
  if (!profile) return emptyProfile;
  return {
    headline: profile.headline ?? null,
    current_title: profile.current_title ?? null,
    summary: profile.summary ?? null,
    years_experience: profile.years_experience ?? null,
    target_roles: profile.target_roles ?? [],
    location_text: profile.location_text ?? null,
    work_modes: profile.work_modes ?? [],
    minimum_compensation: profile.minimum_compensation ?? null,
    experiences: profile.experiences ?? [],
    education: profile.education ?? [],
    skills: profile.skills ?? [],
  };
}

export function ProfileView() {
  const queryClient = useQueryClient();
  const profile = useQuery({ queryKey: ["profile"], queryFn: ({ signal }) => api.profile.get(signal) });
  const [draftOverride, setDraft] = useState<ProfileWrite | null>(null);
  const [role, setRole] = useState("");
  const [skill, setSkill] = useState("");
  const draft = draftOverride ?? toProfileWrite(profile.data);

  const save = useMutation({
    mutationFn: () => api.profile.save(draft),
    onSuccess: (data) => {
      queryClient.setQueryData(["profile"], data);
      setDraft(toProfileWrite(data));
      toast.success("Profile saved");
    },
    onError: (error) => toast.error(error.message),
  });

  if (profile.isLoading) return <Skeleton className="page-skeleton" />;
  if (profile.isError) return <ErrorState message={profile.error.message} retry={() => profile.refetch()} />;

  const experiences = draft.experiences ?? [];
  const education = draft.education ?? [];
  const skills = draft.skills ?? [];
  const targetRoles = draft.target_roles ?? [];
  const workModes = draft.work_modes ?? [];

  return (
    <>
      <PageHeader eyebrow="Profile" title="Help ApplyAI understand what you want next." description="Keep your experience, skills, and job preferences accurate so recommendations and preparation stay relevant to you." action={<Button disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save profile"}</Button>} />
      <div className="profile-sections">
        <Card className="profile-card">
          <h2>About you</h2>
          <div className="form-grid">
            <Field label="Current title" htmlFor="profile-title"><Input id="profile-title" value={draft.current_title ?? ""} onChange={(event) => setDraft({ ...draft, current_title: event.target.value || null })} /></Field>
            <Field label="Years of experience" htmlFor="profile-years"><Input id="profile-years" type="number" min="0" max="80" value={draft.years_experience ?? ""} onChange={(event) => setDraft({ ...draft, years_experience: event.target.value ? Number(event.target.value) : null })} /></Field>
            <Field className="full-width" label="Headline" htmlFor="profile-headline"><Input id="profile-headline" value={draft.headline ?? ""} onChange={(event) => setDraft({ ...draft, headline: event.target.value || null })} /></Field>
            <Field className="full-width" label="Summary" htmlFor="profile-summary"><Textarea id="profile-summary" value={draft.summary ?? ""} onChange={(event) => setDraft({ ...draft, summary: event.target.value || null })} /></Field>
          </div>
        </Card>

        <Card className="profile-card">
          <div className="section-header"><div><h2>Experience</h2><p>Keep the work you want ApplyAI to consider accurate and current.</p></div><Button variant="secondary" size="small" onClick={() => setDraft({ ...draft, experiences: [...experiences, { company_name: "", title: "", description: null, provenance: "USER_ENTERED" }] })}><Plus size={15} />Add</Button></div>
          <div className="list-stack">{experiences.map((item, index) => <div className="repeater-item form-grid" key={item.id ?? `new-experience-${index}`}>
            <Field label="Company" htmlFor={`profile-company-${index}`}><Input id={`profile-company-${index}`} value={item.company_name} onChange={(event) => setDraft({ ...draft, experiences: experiences.map((value, i) => i === index ? { ...value, company_name: event.target.value } : value) })} /></Field>
            <Field label="Title" htmlFor={`profile-role-${index}`}><Input id={`profile-role-${index}`} value={item.title} onChange={(event) => setDraft({ ...draft, experiences: experiences.map((value, i) => i === index ? { ...value, title: event.target.value } : value) })} /></Field>
            <Field className="full-width" label="Description" htmlFor={`profile-exp-description-${index}`}><Textarea id={`profile-exp-description-${index}`} value={item.description ?? ""} onChange={(event) => setDraft({ ...draft, experiences: experiences.map((value, i) => i === index ? { ...value, description: event.target.value || null, provenance: "USER_ENTERED" } : value) })} /></Field>
            <Button className="remove-item" size="icon" variant="ghost" aria-label="Remove experience" onClick={() => setDraft({ ...draft, experiences: experiences.filter((_, i) => i !== index) })}><X size={16} /></Button>
          </div>)}</div>
        </Card>

        <Card className="profile-card">
          <div className="section-header"><div><h2>Education</h2><p>Add the education you want included in your career profile.</p></div><Button variant="secondary" size="small" onClick={() => setDraft({ ...draft, education: [...education, { institution: "", degree: null, field_of_study: null, provenance: "USER_ENTERED" }] })}><Plus size={15} />Add</Button></div>
          <div className="list-stack">{education.map((item, index) => <div className="repeater-item form-grid" key={item.id ?? `new-education-${index}`}>
            <Field className="full-width" label="Institution" htmlFor={`profile-institution-${index}`}><Input id={`profile-institution-${index}`} value={item.institution} onChange={(event) => setDraft({ ...draft, education: education.map((value, i) => i === index ? { ...value, institution: event.target.value } : value) })} /></Field>
            <Field label="Degree" htmlFor={`profile-degree-${index}`}><Input id={`profile-degree-${index}`} value={item.degree ?? ""} onChange={(event) => setDraft({ ...draft, education: education.map((value, i) => i === index ? { ...value, degree: event.target.value || null, provenance: "USER_ENTERED" } : value) })} /></Field>
            <Field label="Field of study" htmlFor={`profile-field-${index}`}><Input id={`profile-field-${index}`} value={item.field_of_study ?? ""} onChange={(event) => setDraft({ ...draft, education: education.map((value, i) => i === index ? { ...value, field_of_study: event.target.value || null, provenance: "USER_ENTERED" } : value) })} /></Field>
            <Button className="remove-item" size="icon" variant="ghost" aria-label="Remove education" onClick={() => setDraft({ ...draft, education: education.filter((_, i) => i !== index) })}><X size={16} /></Button>
          </div>)}</div>
        </Card>

        <Card className="profile-card">
          <h2>Skills</h2>
          <div className="button-row"><Input aria-label="Add skill" value={skill} onChange={(event) => setSkill(event.target.value)} placeholder="Add a skill" /><Button variant="secondary" onClick={() => { if (skill.trim()) setDraft({ ...draft, skills: [...skills, { name: skill.trim(), provenance: "USER_ENTERED" }] }); setSkill(""); }}>Add skill</Button></div>
          <div className="chips" style={{ marginTop: 14 }}>{skills.map((item, index) => <button className="ui-badge" type="button" key={`${item.name}-${index}`} onClick={() => setDraft({ ...draft, skills: skills.filter((_, i) => i !== index) })}>{item.name} ×</button>)}</div>
        </Card>

        <Card className="profile-card">
          <h2>What you’re looking for</h2>
          <div className="form-stack">
            <Field label="Preferred location" htmlFor="profile-location"><Input id="profile-location" value={draft.location_text ?? ""} onChange={(event) => setDraft({ ...draft, location_text: event.target.value || null })} /></Field>
            <div><strong>Work modes</strong><div className="choice-grid" style={{ marginTop: 8 }}>{["REMOTE", "HYBRID", "ONSITE"].map((mode) => <label className="choice" key={mode}><input type="checkbox" checked={workModes.includes(mode)} onChange={(event) => setDraft({ ...draft, work_modes: event.target.checked ? [...workModes, mode] : workModes.filter((value) => value !== mode) })} />{mode}</label>)}</div></div>
            <Field label="Minimum compensation (USD)" htmlFor="profile-comp"><Input id="profile-comp" type="number" min="0" step="5000" value={draft.minimum_compensation ?? ""} onChange={(event) => setDraft({ ...draft, minimum_compensation: event.target.value ? Number(event.target.value) : null })} /></Field>
            <div><strong>Target roles</strong><div className="button-row" style={{ marginTop: 8 }}><Input aria-label="Add target role" value={role} onChange={(event) => setRole(event.target.value)} placeholder="Senior Data Engineer" /><Button variant="secondary" onClick={() => { if (role.trim()) setDraft({ ...draft, target_roles: [...new Set([...targetRoles, role.trim()])] }); setRole(""); }}>Add role</Button></div><div className="chips" style={{ marginTop: 12 }}>{targetRoles.map((item, index) => <Badge key={item} tone={index === 0 ? "success" : "neutral"}>{index === 0 ? `Primary · ${item}` : item}<button aria-label={`Remove ${item}`} style={{ border: 0, background: "transparent", cursor: "pointer" }} onClick={() => setDraft({ ...draft, target_roles: targetRoles.filter((value) => value !== item) })}>×</button></Badge>)}</div></div>
          </div>
        </Card>
      </div>
    </>
  );
}
