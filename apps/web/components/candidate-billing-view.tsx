"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, CreditCard, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Badge, Button, Card, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { platformApi } from "@/lib/api/platform-client";
import { titleCase } from "@/lib/utils";

function entitlementItems(entitlements: unknown) {
  if (!entitlements || typeof entitlements !== "object") return [];
  return Object.entries(entitlements as Record<string, unknown>)
    .filter(([, value]) => value !== false && value !== null && value !== undefined)
    .slice(0, 8)
    .map(([key, value]) => {
      const label = titleCase(key.replaceAll("_", " "));
      if (typeof value === "boolean") return label;
      if (typeof value === "number") return `${label}: ${value.toLocaleString()}`;
      if (typeof value === "string") return `${label}: ${titleCase(value)}`;
      return label;
    });
}

export function CandidateBillingView() {
  const subscription = useQuery({ queryKey: ["billing-subscription"], queryFn: platformApi.billing.subscription });
  const checkout = useMutation({
    mutationFn: platformApi.billing.checkout,
    onSuccess: (data) => {
      if (data.checkout_url) window.location.assign(data.checkout_url);
    },
    onError: () => toast.error("Billing checkout is not configured in this environment."),
  });

  if (subscription.isLoading) return <Skeleton className="page-skeleton" />;
  if (subscription.isError) return <ErrorState message={subscription.error.message} retry={() => subscription.refetch()} />;

  const data = subscription.data ?? {};
  const plan = String(data.plan ?? "FREE");
  const status = String(data.status ?? "ACTIVE");
  const features = entitlementItems(data.entitlements);

  return (
    <>
      <PageHeader
        eyebrow="Plan"
        title="Choose the support that fits your search."
        description="Your plan controls how much AI-assisted preparation and career support is available to your account."
      />

      <div className="cx-plan-layout">
        <Card className="cx-current-plan">
          <div className="cx-plan-icon"><CreditCard size={20} /></div>
          <div className="cx-plan-heading">
            <div><p className="eyebrow">Current plan</p><h2>{titleCase(plan)}</h2></div>
            <Badge tone={status === "ACTIVE" ? "success" : "warning"}>{titleCase(status)}</Badge>
          </div>
          {features.length ? (
            <div className="cx-plan-features">
              {features.map((feature) => <div key={feature}><Check size={15} />{feature}</div>)}
            </div>
          ) : <p className="muted">Your account is ready for the core ApplyAI experience.</p>}
        </Card>

        <div className="cx-plan-options">
          <Card className="cx-plan-option">
            <span className="cx-action-label">For active job searches</span>
            <h2>Pro</h2>
            <p>More room for personalized matching, resume preparation, and interview support.</p>
            <Button onClick={() => checkout.mutate("PRO")} disabled={checkout.isPending}><Sparkles size={16} />Choose Pro</Button>
          </Card>
          <Card className="cx-plan-option">
            <span className="cx-action-label">For teams</span>
            <h2>Team</h2>
            <p>Shared access for organizations supporting multiple people or career workflows.</p>
            <Button variant="secondary" onClick={() => checkout.mutate("TEAM")} disabled={checkout.isPending}>Explore Team</Button>
          </Card>
        </div>
      </div>
    </>
  );
}
