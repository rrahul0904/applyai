"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Card, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api/client";

export function SettingsView() {
  const me = useQuery({ queryKey: ["me"], queryFn: ({ signal }) => api.auth.me(signal) });
  const profile = useQuery({ queryKey: ["profile"], queryFn: ({ signal }) => api.profile.get(signal) });

  if (me.isLoading || profile.isLoading) return <Skeleton className="page-skeleton" />;
  if (me.isError || profile.isError || !me.data) return <ErrorState message={me.error?.message ?? profile.error?.message} retry={() => location.reload()} />;

  return (
    <>
      <PageHeader eyebrow="Settings" title="Account and candidate preferences." description="Only settings backed by real platform behavior are shown here." />
      <div className="profile-sections">
        <Card className="profile-card">
          <h2>Account</h2>
          <div className="completion-summary">
            <div className="summary-row"><span>Email</span><strong>{me.data.email}</strong></div>
            <div className="summary-row"><span>Account status</span><strong>{me.data.account_status}</strong></div>
            <div className="summary-row"><span>Onboarding</span><strong>{me.data.onboarding_completed ? "Complete" : me.data.onboarding_stage.replaceAll("_", " ")}</strong></div>
          </div>
          <p className="muted">Authentication and sign-out are managed by the active identity provider in the candidate shell.</p>
        </Card>
        <Card className="profile-card">
          <h2>Job preferences</h2>
          <div className="completion-summary">
            <div className="summary-row"><span>Target roles</span><strong>{profile.data?.target_roles?.join(", ") || "Not set"}</strong></div>
            <div className="summary-row"><span>Location</span><strong>{profile.data?.location_text || "Flexible"}</strong></div>
            <div className="summary-row"><span>Work modes</span><strong>{profile.data?.work_modes?.join(", ") || "Not set"}</strong></div>
          </div>
          <Link className="ui-button ui-button-secondary ui-button-small" href="/profile">Edit profile and preferences</Link>
        </Card>
        <Card className="profile-card">
          <h2>Privacy</h2>
          <p className="muted">Resumes, application notes, compensation preferences, and candidate profile data are account-scoped. Public profile controls are not exposed until a real discoverability workflow exists.</p>
        </Card>
      </div>
    </>
  );
}
