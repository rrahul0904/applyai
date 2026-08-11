"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Card, ErrorState, PageHeader, Skeleton, Button } from "@/components/ui";
import { api } from "@/lib/api/client";

async function backend<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend${path}`, { ...init, headers: init.body ? { "content-type": "application/json", ...init.headers } : init.headers });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.error?.message ?? "Request failed");
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function SettingsView() {
  const me = useQuery({ queryKey: ["me"], queryFn: ({ signal }) => api.auth.me(signal) });
  const profile = useQuery({ queryKey: ["profile"], queryFn: ({ signal }) => api.profile.get(signal) });
  const [deleting, setDeleting] = useState(false);

  if (me.isLoading || profile.isLoading) return <Skeleton className="page-skeleton" />;
  if (me.isError || profile.isError || !me.data) return <ErrorState message={me.error?.message ?? profile.error?.message} retry={() => location.reload()} />;

  const exportData = async () => {
    try {
      const data = await backend<Record<string, unknown>>("/account/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "applyai-account-export.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Export failed");
    }
  };

  const deleteAccount = async () => {
    if (!window.confirm("Permanently delete your ApplyAI data? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await backend("/account", { method: "DELETE" });
      toast.success("Your ApplyAI data has been deleted.");
      window.location.assign("/");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Deletion failed");
      setDeleting(false);
    }
  };

  return (
    <>
      <PageHeader eyebrow="Settings" title="Your account, preferences, and privacy." description="Manage the details that shape your ApplyAI experience and control the data attached to your account." />
      <div className="profile-sections">
        <Card className="profile-card">
          <h2>Account</h2>
          <div className="completion-summary">
            <div className="summary-row"><span>Email</span><strong>{me.data.email}</strong></div>
            <div className="summary-row"><span>Status</span><strong>{me.data.account_status}</strong></div>
            <div className="summary-row"><span>Getting started</span><strong>{me.data.onboarding_completed ? "Complete" : me.data.onboarding_stage.replaceAll("_", " ")}</strong></div>
          </div>
        </Card>

        <Card className="profile-card">
          <h2>Job preferences</h2>
          <div className="completion-summary">
            <div className="summary-row"><span>Target roles</span><strong>{profile.data?.target_roles?.join(", ") || "Not set"}</strong></div>
            <div className="summary-row"><span>Location</span><strong>{profile.data?.location_text || "Flexible"}</strong></div>
            <div className="summary-row"><span>Work modes</span><strong>{profile.data?.work_modes?.join(", ") || "Not set"}</strong></div>
          </div>
          <Link className="ui-button ui-button-secondary ui-button-small" href="/profile">Edit profile</Link>
        </Card>

        <Card className="profile-card">
          <h2>Alerts</h2>
          <p className="muted">Choose the searches and follow-ups you want ApplyAI to keep visible.</p>
          <Link className="ui-button ui-button-secondary ui-button-small" href="/alerts">Manage alerts</Link>
        </Card>

        <Card className="profile-card">
          <h2>Plan</h2>
          <p className="muted">Review your current plan and available career support.</p>
          <Link className="ui-button ui-button-secondary ui-button-small" href="/billing">View plan</Link>
        </Card>

        <Card className="profile-card">
          <h2>Your data</h2>
          <p className="muted">Download a copy of your ApplyAI data or permanently remove it from the platform.</p>
          <div className="button-row"><Button variant="secondary" onClick={exportData}>Download my data</Button><Button variant="ghost" disabled={deleting} onClick={deleteAccount}>{deleting ? "Deleting…" : "Delete my data"}</Button></div>
        </Card>
      </div>
    </>
  );
}
