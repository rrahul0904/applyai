"use client";

import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, FileText, MapPin, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

import { ResumeShareIntelligenceView } from "@/components/resume-share-intelligence-view";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";

export function CandidatePortfolioView() {
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: ({ signal }) => api.profile.get(signal),
  });

  if (profile.isLoading) return <Skeleton className="page-skeleton" />;
  if (profile.isError) return <ErrorState message={profile.error.message} retry={() => profile.refetch()} />;

  const value = profile.data;
  if (!value) {
    return <Card>
      <EmptyState
        icon={<Sparkles size={22} />}
        title="Build your verified career profile first"
        description="Your portfolio is generated from the profile and resume evidence you control. ApplyAI does not invent experience, skills, or accomplishments."
        action={<Link className="ui-button ui-button-primary" href="/profile">Create profile</Link>}
      />
    </Card>;
  }

  const skills = value.skills ?? [];
  const experiences = value.experiences ?? [];
  const education = value.education ?? [];
  const targetRoles = value.target_roles ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Career Portfolio"
        title={value.headline || value.current_title || "Your verified professional profile"}
        description="A candidate-controlled professional presence built from verified profile and resume evidence. Share only what you intentionally publish."
        action={<Link className="ui-button ui-button-secondary" href="/profile">Edit profile</Link>}
      />

      <div className="dashboard-grid">
        <Card>
          <p className="eyebrow">Current role</p>
          <h2>{value.current_title || "Add your current title"}</h2>
          <p>{value.years_experience != null ? `${value.years_experience} years of experience` : "Experience length not set"}</p>
        </Card>
        <Card>
          <p className="eyebrow">Target roles</p>
          <h2>{targetRoles.length}</h2>
          <p>{targetRoles.slice(0, 3).join(" · ") || "Add roles you are targeting"}</p>
        </Card>
        <Card>
          <p className="eyebrow">Verified skills</p>
          <h2>{skills.length}</h2>
          <p>{skills.slice(0, 5).map((item) => item.name).join(" · ") || "Add skills to your profile"}</p>
        </Card>
      </div>

      <Card className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Professional snapshot</p>
            <h2>{value.headline || value.current_title || "Career profile"}</h2>
          </div>
          <Badge tone="success"><ShieldCheck size={14} /> Candidate controlled</Badge>
        </div>
        {value.summary ? <p>{value.summary}</p> : <p className="muted">Add a profile summary to make this snapshot more useful.</p>}
        <div className="button-row">
          {value.location_text ? <Badge><MapPin size={13} />{value.location_text}</Badge> : null}
          {value.work_modes?.map((mode) => <Badge key={mode}>{mode}</Badge>)}
        </div>
      </Card>

      <div className="detail-grid">
        <div className="detail-main">
          <Card className="detail-section">
            <div className="section-header"><h2><BriefcaseBusiness size={18} /> Experience</h2><Badge>{experiences.length}</Badge></div>
            <div className="list-stack">
              {experiences.map((item, index) => (
                <div className="note" key={item.id ?? `experience-${index}`}>
                  <strong>{item.title}</strong>
                  <p>{item.company_name}</p>
                  {item.description ? <p>{item.description}</p> : null}
                  <span className="eyebrow">{item.provenance?.replaceAll("_", " ") || "PROFILE"}</span>
                </div>
              ))}
              {!experiences.length ? <p>No experience entries yet.</p> : null}
            </div>
          </Card>

          <Card className="detail-section">
            <div className="section-header"><h2><FileText size={18} /> Education</h2><Badge>{education.length}</Badge></div>
            <div className="list-stack">
              {education.map((item, index) => (
                <div className="note" key={item.id ?? `education-${index}`}>
                  <strong>{item.degree || item.field_of_study || "Education"}</strong>
                  <p>{item.institution}{item.field_of_study ? ` · ${item.field_of_study}` : ""}</p>
                </div>
              ))}
              {!education.length ? <p>No education entries yet.</p> : null}
            </div>
          </Card>
        </div>

        <aside className="detail-aside">
          <Card className="sticky-actions">
            <h2>Skills</h2>
            <div className="chips">
              {skills.map((item) => <Badge key={item.id ?? item.name} tone="info">{item.name}</Badge>)}
            </div>
            {!skills.length ? <p className="muted">No skills added yet.</p> : null}
            <h3>Privacy boundary</h3>
            <p>Profile editing stays private. Public resume links are separate, revocable, optionally expiring, and created only when you choose to share.</p>
          </Card>
        </aside>
      </div>

      <ResumeShareIntelligenceView />
    </>
  );
}
