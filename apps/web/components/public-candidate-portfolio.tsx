"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Github, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui";

type PublicPortfolio = {
  slug: string;
  theme: string;
  indexing_allowed: boolean;
  headline: string | null;
  about: string | null;
  profile: { current_title: string | null; summary: string | null };
  experience: Array<{ company_name: string; title: string; start_date: string | null; end_date: string | null; description: string | null }>;
  education: Array<{ institution: string; degree: string | null; field_of_study: string | null; start_date: string | null; end_date: string | null }>;
  skills: string[];
  projects: Array<{ id: string; title: string; summary: string; role: string | null; technologies: string[]; verified_outcome: string | null; project_url: string | null; repository_url: string | null; media_url: string | null; project_date: string | null; visible: boolean }>;
  contact_enabled: boolean;
  privacy: { candidate_opt_in: true; raw_resume_exposed: false; indexing_allowed: boolean };
};

async function loadPortfolio(slug: string, signal?: AbortSignal): Promise<PublicPortfolio> {
  const response = await fetch(`/api/public-backend/growth/public/portfolio/${slug}`, { signal, cache: "no-store" });
  if (!response.ok) throw new Error(response.status === 404 ? "This portfolio is private or unavailable." : "This portfolio could not be loaded.");
  return response.json() as Promise<PublicPortfolio>;
}

export function PublicCandidatePortfolio({ slug }: { slug: string }) {
  const portfolio = useQuery({ queryKey: ["public-portfolio", slug], queryFn: ({ signal }) => loadPortfolio(slug, signal), retry: false });
  if (portfolio.isLoading) return <main className="public-page"><p>Loading portfolio…</p></main>;
  if (portfolio.isError || !portfolio.data) return <main className="public-page"><h1>Portfolio unavailable</h1><p>{portfolio.error?.message}</p></main>;
  const data = portfolio.data;
  return <main className={`public-page public-portfolio public-portfolio-${data.theme.toLowerCase()}`}>
    <header className="detail-section">
      <p className="eyebrow">ApplyAI verified-evidence portfolio</p>
      <h1>{data.headline ?? data.profile.current_title ?? "Candidate portfolio"}</h1>
      {data.about ?? data.profile.summary ? <p className="lead">{data.about ?? data.profile.summary}</p> : null}
      <p className="muted"><ShieldCheck size={15} style={{verticalAlign:"text-bottom"}} /> Published explicitly by the candidate. ApplyAI does not expose the private résumé file on this page.</p>
    </header>

    {data.skills.length ? <section className="detail-section"><h2>Skills</h2><div className="button-row">{data.skills.map((skill) => <Badge key={skill}>{skill}</Badge>)}</div></section> : null}

    {data.projects.length ? <section className="detail-section"><h2>Selected projects</h2><div className="list-stack">{data.projects.map((project) => <article key={project.id}><h3>{project.title}</h3>{project.role ? <p className="eyebrow">{project.role}</p> : null}<p>{project.summary}</p>{project.verified_outcome ? <p><strong>Candidate-provided outcome:</strong> {project.verified_outcome}</p> : null}<div className="button-row">{project.technologies.map((technology) => <Badge key={technology}>{technology}</Badge>)}{project.project_url ? <a href={project.project_url} target="_blank" rel="noreferrer"><ExternalLink size={15}/> Project</a> : null}{project.repository_url ? <a href={project.repository_url} target="_blank" rel="noreferrer"><Github size={15}/> Repository</a> : null}</div></article>)}</div></section> : null}

    {data.experience.length ? <section className="detail-section"><h2>Experience</h2><div className="list-stack">{data.experience.map((experience, index) => <article key={`${experience.company_name}-${experience.title}-${index}`}><h3>{experience.title}</h3><p className="eyebrow">{experience.company_name}</p>{experience.description ? <p>{experience.description}</p> : null}</article>)}</div></section> : null}

    {data.education.length ? <section className="detail-section"><h2>Education</h2><div className="list-stack">{data.education.map((education, index) => <article key={`${education.institution}-${index}`}><h3>{education.degree ?? education.field_of_study ?? "Education"}</h3><p>{education.institution}</p></article>)}</div></section> : null}

    <footer className="detail-section"><p className="muted">Theme: {data.theme.toLowerCase()} · Search indexing {data.indexing_allowed ? "allowed" : "disabled"} by the candidate.</p></footer>
  </main>;
}
