"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { JobWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Skeleton } from "@/components/ui";
import { platformApi } from "@/lib/api/platform-client";

export function CandidateAlertsView() {
  const queryClient = useQueryClient();
  const notifications = useQuery({ queryKey: ["notifications"], queryFn: platformApi.notifications.list });
  const searches = useQuery({ queryKey: ["saved-searches"], queryFn: platformApi.savedSearches.list });
  const [name, setName] = useState("");
  const [keyword, setKeyword] = useState("");

  const create = useMutation({
    mutationFn: () => platformApi.savedSearches.create({ name, query: { q: keyword }, alerts_enabled: true, minimum_match_score: 70 }),
    onSuccess: async () => {
      setName("");
      setKeyword("");
      await queryClient.invalidateQueries({ queryKey: ["saved-searches"] });
      toast.success("Job alert created");
    },
  });
  const markRead = useMutation({
    mutationFn: platformApi.notifications.read,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <>
      <JobWorkspaceTabs activeHref="/alerts" />
      <PageHeader
        eyebrow="Stay ahead"
        title="Let the right opportunities come to you."
        description="Create focused job alerts and keep important follow-ups in one lightweight inbox."
      />

      <div className="cx-alert-layout">
        <Card className="cx-home-panel">
          <div className="cx-section-heading compact">
            <div><p className="eyebrow">Job alerts</p><h2>Watch what matters</h2></div>
          </div>
          <form className="cx-alert-form" onSubmit={(event) => { event.preventDefault(); if (name.trim() && keyword.trim()) create.mutate(); }}>
            <Field label="Alert name" htmlFor="alert-name"><Input id="alert-name" placeholder="e.g. Staff Data Engineering" value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Keyword" htmlFor="alert-keyword"><Input id="alert-keyword" placeholder="Role, company, or skill" value={keyword} onChange={(e) => setKeyword(e.target.value)} /></Field>
            <Button type="submit" disabled={!name.trim() || !keyword.trim() || create.isPending}><Plus size={16} />Create alert</Button>
          </form>
          {searches.isLoading ? <Skeleton className="skeleton-tall" /> : searches.data?.length ? (
            <div className="cx-alert-list">
              {searches.data.map((search) => (
                <div className="cx-alert-row" key={search.id}>
                  <div><strong>{search.name}</strong><span>Notify me when a strong match appears</span></div>
                  <Badge tone={search.alerts_enabled ? "success" : "warning"}>{search.alerts_enabled ? "On" : "Paused"}</Badge>
                </div>
              ))}
            </div>
          ) : <p className="muted">No alerts yet. Create one for the searches you care about most.</p>}
        </Card>

        <Card className="cx-home-panel">
          <div className="cx-section-heading compact">
            <div><p className="eyebrow">Inbox</p><h2>Updates & follow-ups</h2></div>
          </div>
          {notifications.isLoading ? <Skeleton className="skeleton-tall" /> : notifications.data?.length ? (
            <div className="cx-notification-list">
              {notifications.data.map((item) => (
                <article className={item.read_at ? "cx-notification read" : "cx-notification"} key={item.id}>
                  <div className="cx-notification-icon"><Bell size={16} /></div>
                  <div><strong>{item.title}</strong><p>{item.body}</p>{item.action_url ? <Link href={item.action_url}>Open <span aria-hidden="true">→</span></Link> : null}</div>
                  {item.read_at ? <Check size={17} aria-label="Read" /> : <Button size="small" variant="ghost" onClick={() => markRead.mutate(item.id)}>Mark read</Button>}
                </article>
              ))}
            </div>
          ) : (
            <EmptyState icon={<Bell size={22} />} title="You're all caught up" description="New job-match alerts, interview reminders, and follow-ups will appear here." />
          )}
        </Card>
      </div>
    </>
  );
}
