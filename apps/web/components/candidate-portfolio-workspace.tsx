"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Globe2, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, ErrorState, Input, NativeSelect, PageHeader, Textarea } from "@/components/ui";
import { growthApi } from "@/lib/api/growth";

const visibilityKeys = ["headline", "about", "experience", "education", "skills", "projects"] as const;

export function CandidatePortfolioWorkspace() {
  const queryClient = useQueryClient();
  const portfolio = useQuery({ queryKey: ["candidate-portfolio"], queryFn: ({ signal }) => growthApi.portfolio.get(signal) });
  const [slug, setSlug] = useState("");
  const [headline, setHeadline] = useState("");
  const [about, setAbout] = useState("");
  const [theme, setTheme] = useState("PROFESSIONAL");
  const [published, setPublished] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [visibility, setVisibility] = useState<Record<string, boolean>>({});
  const [projectTitle, setProjectTitle] = useState("");
  const [projectSummary, setProjectSummary] = useState("");
  const [projectTech, setProjectTech] = useState("");

  useEffect(() => {
    if (!portfolio.data) return;
    setSlug(portfolio.data.slug ?? portfolio.data.suggested_slug ?? "");
    setHeadline(portfolio.data.headline ?? "");
    setAbout(portfolio.data.about ?? "");
    setTheme(portfolio.data.theme ?? "PROFESSIONAL");
    setPublished(Boolean(portfolio.data.published));
    setIndexing(Boolean(portfolio.data.indexing_allowed));
    setVisibility(portfolio.data.visibility ?? {});
  }, [portfolio.data]);

  const save = useMutation({
    mutationFn: () => growthApi.portfolio.save({
      slug,
      headline: headline || null,
      about: about || null,
      theme,
      published,
      indexing_allowed: indexing,
      contact_enabled: false,
      visibility,
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["candidate-portfolio"] });
      toast.success(published ? "Portfolio published" : "Portfolio settings saved");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not save portfolio"),
  });
  const addProject = useMutation({
    mutationFn: () => growthApi.portfolio.createProject({
      title: projectTitle,
      summary: projectSummary,
      technologies: projectTech.split(",").map((item) => item.trim()).filter(Boolean),
      visible: true,
    }),
    onSuccess: async () => {
      setProjectTitle(""); setProjectSummary(""); setProjectTech("");
      await queryClient.invalidateQueries({ queryKey: ["candidate-portfolio"] });
      toast.success("Portfolio project added");
    },
  });
  const removeProject = useMutation({
    mutationFn: growthApi.portfolio.deleteProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["candidate-portfolio"] }),
  });

  if (portfolio.isError) return <ErrorState message={portfolio.error.message} retry={() => portfolio.refetch()} />;

  return <>
    <PageHeader
      eyebrow="Portfolio Identity"
      title="Publish only what you choose."
      description="Build an opt-in career portfolio from candidate-owned and verified evidence. Nothing becomes public until you publish it."
      action={portfolio.data?.public_path && portfolio.data.published ? <Link className="ui-button ui-button-secondary" href={portfolio.data.public_path} target="_blank"><ExternalLink size={16}/>View public portfolio</Link> : undefined}
    />
    <div className="detail-grid">
      <div className="detail-main list-stack">
        <Card className="detail-section">
          <div className="section-header"><div><h2>Publishing controls</h2><p>Choose a public slug, original ApplyAI theme, and exactly which evidence sections are visible.</p></div><Badge tone={published ? "success" : undefined}>{published ? "Published" : "Private"}</Badge></div>
          <div className="form-grid">
            <label className="form-field"><span>Public slug</span><Input value={slug} onChange={(event) => setSlug(event.target.value)} placeholder="your-name" /></label>
            <label className="form-field"><span>Theme</span><NativeSelect value={theme} onChange={(event) => setTheme(event.target.value)}><option value="PROFESSIONAL">Professional</option><option value="MINIMAL">Minimal</option><option value="TECHNICAL">Technical</option><option value="PORTFOLIO">Portfolio</option></NativeSelect></label>
          </div>
          <label className="form-field"><span>Headline</span><Input value={headline} maxLength={240} onChange={(event) => setHeadline(event.target.value)} placeholder="Your candidate-owned public headline" /></label>
          <label className="form-field"><span>About</span><Textarea value={about} maxLength={4000} rows={6} onChange={(event) => setAbout(event.target.value)} placeholder="Use claims you are comfortable defending." /></label>
          <fieldset className="form-field"><legend>Visible sections</legend><div className="button-row">{visibilityKeys.map((key) => <label key={key}><input type="checkbox" checked={visibility[key] ?? true} onChange={(event) => setVisibility((current) => ({ ...current, [key]: event.target.checked }))} /> {key}</label>)}</div></fieldset>
          <div className="button-row">
            <label><input type="checkbox" checked={published} onChange={(event) => setPublished(event.target.checked)} /> Publish portfolio</label>
            <label><input type="checkbox" checked={indexing} onChange={(event) => setIndexing(event.target.checked)} /> Allow search indexing</label>
            <Button onClick={() => save.mutate()} disabled={!slug.trim() || save.isPending}><Globe2 size={16}/>Save portfolio</Button>
          </div>
          <p className="muted">Publishing is explicit and reversible. Unpublishing makes `/u/{slug || "your-slug"}` unavailable immediately.</p>
        </Card>

        <Card className="detail-section">
          <div className="section-header"><div><h2>Project showcase</h2><p>Add candidate-owned projects without turning AI suggestions into invented outcomes.</p></div></div>
          <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); if (projectTitle.trim() && projectSummary.trim()) addProject.mutate(); }}>
            <label className="form-field"><span>Project title</span><Input value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} /></label>
            <label className="form-field"><span>Technologies</span><Input value={projectTech} onChange={(event) => setProjectTech(event.target.value)} placeholder="Python, PostgreSQL, Next.js" /></label>
            <label className="form-field"><span>What you did</span><Textarea value={projectSummary} onChange={(event) => setProjectSummary(event.target.value)} rows={5} /></label>
            <Button type="submit" disabled={!projectTitle.trim() || !projectSummary.trim() || addProject.isPending}><Plus size={16}/>Add project</Button>
          </form>
        </Card>

        {(portfolio.data?.projects ?? []).map((project) => <Card className="detail-section" key={project.id}><div className="section-header"><div><h2>{project.title}</h2><p>{project.summary}</p></div><Button variant="ghost" size="small" onClick={() => removeProject.mutate(project.id)}><Trash2 size={15}/>Remove</Button></div>{project.technologies.length ? <div className="button-row">{project.technologies.map((technology) => <Badge key={technology}>{technology}</Badge>)}</div> : null}</Card>)}
      </div>
      <aside className="detail-aside"><Card className="sticky-actions"><h2>Privacy boundary</h2><p>ApplyAI never publishes your portfolio automatically. Résumé files remain private unless you separately create a Resume Share link.</p><Link href="/career" className="ui-button ui-button-ghost">Career evidence</Link><Link href="/resume/signals" className="ui-button ui-button-ghost">Resume Share signals</Link></Card></aside>
    </div>
  </>;
}
