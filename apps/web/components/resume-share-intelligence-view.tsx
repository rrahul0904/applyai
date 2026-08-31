"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Clipboard,
  Download,
  Eye,
  Link2,
  MousePointerClick,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import styles from "@/components/resume-share-intelligence-view.module.css";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";
import {
  resumeShareApi,
  type ResumeShareCreate,
  type ResumeShareSnapshot,
} from "@/lib/api/resume-share";
import { formatDate, titleCase } from "@/lib/utils";

function intentTone(intent: string): "neutral" | "success" | "warning" | "info" {
  if (intent === "DEEP_READ") return "success";
  if (intent === "ENGAGED") return "info";
  return "neutral";
}

function formatDuration(ms: number) {
  if (ms < 1000) return "—";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function absoluteShareUrl(share: ResumeShareSnapshot) {
  if (typeof window === "undefined") return share.public_path;
  return new URL(share.public_path, window.location.origin).toString();
}

export function ResumeShareIntelligenceView() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const jobId = searchParams.get("jobId");
  const suggestedLabel = searchParams.get("label") || "Resume share";
  const suggestedChannel = searchParams.get("channel") || "application";
  const [label, setLabel] = useState(suggestedLabel);
  const [channel, setChannel] = useState(suggestedChannel);
  const [alwaysCurrent, setAlwaysCurrent] = useState(true);
  const [allowDownload, setAllowDownload] = useState(true);
  const [expiryDays, setExpiryDays] = useState("30");

  const resumes = useQuery({
    queryKey: ["resumes"],
    queryFn: ({ signal }) => api.resumes.list(signal),
  });
  const shares = useQuery({
    queryKey: ["resume-shares"],
    queryFn: ({ signal }) => resumeShareApi.list(signal),
    refetchInterval: 15000,
  });

  const create = useMutation({
    mutationFn: (payload: ResumeShareCreate) => resumeShareApi.create(payload),
    onSuccess: async (share) => {
      toast.success("Smart resume link created");
      await queryClient.invalidateQueries({ queryKey: ["resume-shares"] });
      try {
        await navigator.clipboard.writeText(absoluteShareUrl(share));
        toast.success("Share link copied");
      } catch {
        // Clipboard permissions vary by browser; the link remains visible below.
      }
    },
    onError: (error) => toast.error(error.message),
  });

  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "ACTIVE" | "REVOKED" }) =>
      resumeShareApi.update(id, { status }),
    onSuccess: async (_, variables) => {
      toast.success(variables.status === "ACTIVE" ? "Link reactivated" : "Link revoked");
      await queryClient.invalidateQueries({ queryKey: ["resume-shares"] });
    },
    onError: (error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (id: string) => resumeShareApi.remove(id),
    onSuccess: async () => {
      toast.success("Share link deleted");
      await queryClient.invalidateQueries({ queryKey: ["resume-shares"] });
    },
    onError: (error) => toast.error(error.message),
  });

  const handleCreate = () => {
    const days = Number(expiryDays);
    const expiresAt = Number.isFinite(days) && days > 0
      ? new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString()
      : null;
    create.mutate({
      job_id: jobId,
      label: label.trim() || "Resume share",
      channel: channel.trim() || null,
      always_current: alwaysCurrent,
      allow_download: allowDownload,
      expires_at: expiresAt,
    });
  };

  const copy = async (share: ResumeShareSnapshot) => {
    try {
      await navigator.clipboard.writeText(absoluteShareUrl(share));
      toast.success("Share link copied");
    } catch {
      toast.error("Copy was blocked by your browser. Open the link and copy it from the address bar.");
    }
  };

  if (resumes.isError) return <ErrorState message={resumes.error.message} retry={() => resumes.refetch()} />;
  if (shares.isError) return <ErrorState message={shares.error.message} retry={() => shares.refetch()} />;

  return (
    <>
      <PageHeader
        eyebrow="Resume Share Intelligence"
        title="Know what happens after you share your resume."
        description="Create a unique link for a role, referral, or outreach message. ApplyAI records privacy-preserving engagement signals and keeps them attached to your job-search workflow."
        action={<Link className="ui-button ui-button-secondary" href="/resume">Resume library</Link>}
      />

      {resumes.isLoading ? <Skeleton className="page-skeleton" /> : !resumes.data?.length ? (
        <Card>
          <EmptyState
            icon={<Link2 size={22} />}
            title="Upload a resume first"
            description="Resume Share Intelligence needs a secure ApplyAI resume version before it can create a public smart link."
            action={<Link className="ui-button ui-button-primary" href="/resume">Upload resume</Link>}
          />
        </Card>
      ) : (
        <Card className={styles.createCard}>
          <div className={styles.createIntro}>
            <div className={styles.iconBox}><Link2 size={20} /></div>
            <div>
              <p className="eyebrow">Create smart link</p>
              <h2>{jobId ? "Create a role-specific link" : "Create a tracked resume link"}</h2>
              <p>Each link has its own anonymous engagement history, so signals from different applications are never blended together.</p>
            </div>
          </div>
          <div className={styles.formGrid}>
            <label>
              <span>Label</span>
              <input value={label} maxLength={200} onChange={(event) => setLabel(event.target.value)} placeholder="Acme — Data Engineering Manager" />
            </label>
            <label>
              <span>Channel</span>
              <select value={channel} onChange={(event) => setChannel(event.target.value)}>
                <option value="application">Application</option>
                <option value="email">Email</option>
                <option value="linkedin">LinkedIn</option>
                <option value="referral">Referral</option>
                <option value="networking">Networking</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label>
              <span>Expires after</span>
              <select value={expiryDays} onChange={(event) => setExpiryDays(event.target.value)}>
                <option value="7">7 days</option>
                <option value="30">30 days</option>
                <option value="90">90 days</option>
                <option value="0">No expiry</option>
              </select>
            </label>
          </div>
          <div className={styles.toggleRow}>
            <label><input type="checkbox" checked={alwaysCurrent} onChange={(event) => setAlwaysCurrent(event.target.checked)} />Always show my latest uploaded version</label>
            <label><input type="checkbox" checked={allowDownload} onChange={(event) => setAllowDownload(event.target.checked)} />Allow download</label>
          </div>
          <div className="button-row">
            <Button onClick={handleCreate} disabled={create.isPending}>
              <Link2 size={17} />{create.isPending ? "Creating…" : "Create & copy link"}
            </Button>
          </div>
        </Card>
      )}

      <Card className={styles.privacyCard}>
        <ShieldCheck size={20} />
        <div>
          <strong>Privacy-first signals</strong>
          <p>Resume Share Intelligence does not store raw viewer IP addresses, create cross-link browser fingerprints, or claim to know a viewer&apos;s employer. Engagement scores describe observed activity only — never hiring probability.</p>
        </div>
      </Card>

      <section className={styles.section}>
        <div className="section-header">
          <div><p className="eyebrow">Outbox & activity</p><h2>Your smart resume links</h2></div>
          <Button variant="secondary" size="small" onClick={() => shares.refetch()} disabled={shares.isFetching}><RefreshCw size={15} />Refresh</Button>
        </div>

        {shares.isLoading ? (
          <div className="list-stack">{[1, 2].map((item) => <Skeleton key={item} className="skeleton-row" />)}</div>
        ) : shares.data?.length ? (
          <div className={styles.shareList}>
            {shares.data.map((share) => (
              <Card key={share.id} className={styles.shareCard}>
                <div className={styles.shareHeader}>
                  <div>
                    <div className={styles.titleLine}>
                      <h3>{share.label}</h3>
                      <Badge tone={share.active ? "success" : "neutral"}>{share.active ? "Active" : titleCase(share.status)}</Badge>
                    </div>
                    <p>{share.company_name && share.job_title ? `${share.company_name} · ${share.job_title}` : share.filename || "Resume"}</p>
                    <span className={styles.linkText}>{share.public_path}</span>
                  </div>
                  <div className="button-row">
                    <Button size="small" variant="secondary" onClick={() => copy(share)}><Clipboard size={15} />Copy</Button>
                    <a className="ui-button ui-button-ghost ui-button-small" href={share.public_path} target="_blank" rel="noreferrer"><Eye size={15} />Preview</a>
                  </div>
                </div>

                <div className={styles.metrics}>
                  <div><Eye size={17} /><strong>{share.analytics.views}</strong><span>Views</span></div>
                  <div><UserRoundCheck size={17} /><strong>{share.analytics.unique_viewers}</strong><span>Unique</span></div>
                  <div><RefreshCw size={17} /><strong>{share.analytics.returning_viewers}</strong><span>Returned</span></div>
                  <div><Activity size={17} /><strong>{share.analytics.average_interest_score}</strong><span>Avg signal</span></div>
                  <div><Download size={17} /><strong>{share.analytics.downloads}</strong><span>Downloads</span></div>
                  <div><MousePointerClick size={17} /><strong>{share.analytics.link_clicks}</strong><span>Clicks</span></div>
                </div>

                {share.analytics.sessions.length ? (
                  <div className={styles.sessions}>
                    <h4>Viewer sessions</h4>
                    {share.analytics.sessions.slice(0, 5).map((viewer) => (
                      <div className={styles.sessionRow} key={viewer.session_key}>
                        <div>
                          <strong>{viewer.viewer}</strong>
                          <span>Last activity {formatDate(viewer.last_seen_at)}</span>
                        </div>
                        <div className={styles.sessionStats}>
                          <span>{formatDuration(viewer.dwell_ms)} dwell</span>
                          <span>{viewer.scroll_depth}% depth</span>
                          <span>{viewer.views} view{viewer.views === 1 ? "" : "s"}</span>
                        </div>
                        <Badge tone={intentTone(viewer.intent)}>{titleCase(viewer.intent)}</Badge>
                        <strong className={styles.score}>{viewer.interest_score}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={styles.noActivity}>No human engagement recorded yet. Link-preview bots are filtered from viewer metrics.</div>
                )}

                {share.analytics.timeline.length ? (
                  <details className={styles.timeline}>
                    <summary>Recent activity timeline</summary>
                    <div>
                      {share.analytics.timeline.slice(0, 12).map((event, index) => (
                        <p key={`${event.occurred_at}-${event.event_type}-${index}`}>
                          <strong>{event.viewer}</strong> · {titleCase(event.event_type)}
                          {event.event_type === "DWELL" && event.value ? ` · ${formatDuration(event.value)}` : ""}
                          {event.event_type === "SCROLL" && event.value !== null ? ` · ${event.value}%` : ""}
                          <span>{formatDate(event.occurred_at)}</span>
                        </p>
                      ))}
                    </div>
                  </details>
                ) : null}

                <div className={styles.footerActions}>
                  <a className="ui-button ui-button-ghost ui-button-small" href={`/api/backend/resume-shares/${share.id}/export.csv`}><Download size={15} />CSV</a>
                  <Button
                    size="small"
                    variant="secondary"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ id: share.id, status: share.status === "REVOKED" ? "ACTIVE" : "REVOKED" })}
                  >
                    {share.status === "REVOKED" ? "Reactivate" : "Revoke link"}
                  </Button>
                  <Button size="small" variant="ghost" disabled={remove.isPending} onClick={() => remove.mutate(share.id)}><Trash2 size={15} />Delete</Button>
                  <span>Created {formatDate(share.created_at)}{share.expires_at ? ` · Expires ${formatDate(share.expires_at)}` : " · No expiry"}</span>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <Card><EmptyState icon={<Activity size={22} />} title="No smart links yet" description="Create a link above to start a separate engagement timeline for a resume share." /></Card>
        )}
      </section>
    </>
  );
}
