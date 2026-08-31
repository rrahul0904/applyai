"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink, FileText, ShieldCheck } from "lucide-react";
import { useEffect, useRef } from "react";

import styles from "@/components/resume-share-public.module.css";

type PublicResumeShare = {
  label: string;
  candidate_display_name: string;
  headline: string | null;
  filename: string;
  content_type: string;
  allow_download: boolean;
  file_path: string;
  download_path: string;
  privacy_notice: string;
};

async function fetchPublicShare(token: string, signal?: AbortSignal): Promise<PublicResumeShare> {
  const response = await fetch(`/api/public-backend/resume-shares/public/${token}`, {
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    if (response.status === 410) throw new Error("This resume link has expired or was revoked.");
    throw new Error("This resume link is unavailable.");
  }
  return response.json() as Promise<PublicResumeShare>;
}

async function sendEvent(
  token: string,
  sessionId: string,
  eventType: "VIEW" | "DWELL" | "SCROLL" | "LINK_CLICK" | "COPY",
  value?: number,
  target?: string,
) {
  if (!sessionId) return;
  await fetch(`/api/public-backend/resume-shares/public/${token}/events`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      event_type: eventType,
      value,
      target,
    }),
    keepalive: true,
  }).catch(() => undefined);
}

function sessionFor(token: string) {
  const key = `applyai_resume_viewer_${token}`;
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const created = window.crypto.randomUUID();
  window.localStorage.setItem(key, created);
  return created;
}

export function ResumeSharePublic({ token }: { token: string }) {
  const sessionRef = useRef("");
  const viewSentRef = useRef(false);
  const maxScrollRef = useRef(0);
  const share = useQuery({
    queryKey: ["public-resume-share", token],
    queryFn: ({ signal }) => fetchPublicShare(token, signal),
    retry: false,
  });

  useEffect(() => {
    if (!share.data || viewSentRef.current) return;
    viewSentRef.current = true;
    const sessionId = sessionFor(token);
    sessionRef.current = sessionId;
    const startedAt = performance.now();
    void sendEvent(token, sessionId, "VIEW");

    const reportDwell = () => {
      const elapsed = Math.round(performance.now() - startedAt);
      void sendEvent(token, sessionId, "DWELL", elapsed);
    };
    const interval = window.setInterval(reportDwell, 15000);

    const reportScroll = () => {
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      const depth = scrollable <= 0 ? 100 : Math.min(100, Math.round((window.scrollY / scrollable) * 100));
      if (depth >= maxScrollRef.current + 10 || depth === 100) {
        maxScrollRef.current = depth;
        void sendEvent(token, sessionId, "SCROLL", depth);
      }
    };
    reportScroll();
    window.addEventListener("scroll", reportScroll, { passive: true });
    const visibility = () => {
      if (document.visibilityState === "hidden") reportDwell();
    };
    document.addEventListener("visibilitychange", visibility);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("scroll", reportScroll);
      document.removeEventListener("visibilitychange", visibility);
      reportDwell();
    };
  }, [share.data, token]);

  if (share.isLoading) {
    return <main className={styles.shell}><div className={styles.statusCard}>Loading shared resume…</div></main>;
  }
  if (share.isError || !share.data) {
    return <main className={styles.shell}><div className={styles.statusCard}><FileText size={28} /><h1>Resume unavailable</h1><p>{share.error?.message ?? "This link could not be loaded."}</p></div></main>;
  }

  const data = share.data;
  const isPdf = data.content_type === "application/pdf";
  const openResume = () => {
    void sendEvent(token, sessionRef.current, "LINK_CLICK", undefined, "resume-file");
    window.open(data.file_path, "_blank", "noopener,noreferrer");
  };
  const downloadResume = () => {
    const sid = sessionRef.current;
    const separator = data.download_path.includes("?") ? "&" : "?";
    window.location.assign(`${data.download_path}${separator}sid=${encodeURIComponent(sid)}`);
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.brand}>ApplyAI</span>
          <p className={styles.kicker}>Shared resume</p>
          <h1>{data.candidate_display_name}</h1>
          {data.headline ? <p className={styles.headline}>{data.headline}</p> : null}
          <p className={styles.label}>{data.label}</p>
        </div>
        <div className={styles.actions}>
          <button type="button" onClick={openResume}><ExternalLink size={17} />Open resume</button>
          {data.allow_download ? <button type="button" onClick={downloadResume}><Download size={17} />Download</button> : null}
        </div>
      </header>

      <section className={styles.viewer} aria-label="Shared resume document">
        {isPdf ? (
          <iframe src={data.file_path} title={`${data.candidate_display_name} resume`} />
        ) : (
          <div className={styles.documentFallback}>
            <FileText size={44} />
            <h2>{data.filename}</h2>
            <p>This document format is available through the secure file action above.</p>
            <button type="button" onClick={openResume}><ExternalLink size={17} />Open document</button>
          </div>
        )}
      </section>

      <footer className={styles.privacy}>
        <ShieldCheck size={18} />
        <p><strong>Privacy note.</strong> {data.privacy_notice} The owner sees anonymous activity such as views, return visits, time on this page, scroll depth, and downloads.</p>
      </footer>
    </main>
  );
}
