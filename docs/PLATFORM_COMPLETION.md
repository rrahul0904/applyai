# ApplyAI Platform Completion

This document defines the source-complete platform boundary after Career Intelligence V2.

## Candidate product

Canonical authenticated product routes now cover:

- dashboard
- AI Matches
- job search/detail and company intelligence
- saved jobs
- application command center
- Resume Studio
- Career Intelligence / Career Memory
- Interview Copilot and practice history
- networking contacts and recruiter follow-ups
- alerts and saved searches
- candidate analytics
- profile/settings/privacy
- subscription and usage entitlements

Historical `/demo` and `/beta` entry points redirect into the canonical product rather than maintaining parallel behavior.

## Career Intelligence and evaluation

- deterministic explainable ranking remains the safety baseline
- semantic embedding reranking is provider-abstracted with deterministic local execution for CI
- OpenAI embeddings can be enabled by deployment configuration
- AI runs/artifacts retain prompt/model/schema/token/latency/cost telemetry
- golden evaluation data measures Precision@5/10, reciprocal rank, evidence support rate and unsupported references
- operator A/B comparison can reject a prompt/model/ranking variant before rollout

## Resume and application workflow

- master resume ingestion remains versioned/durable
- Resume Studio adds job-specific editable variants and export
- evidence-locked Career Memory is the source for supported candidate claims
- first-party ApplyAI employers support candidate-approved direct submission
- third-party employers use a reviewed external handoff; ApplyAI does not bypass employer authentication, CAPTCHAs or anti-bot controls

## Employer platform

- employer organizations and role-based membership
- operator verification/suspension boundary
- employer job drafts, publishing and closure
- published first-party jobs enter the same canonical candidate search index
- first-party applicants enter the employer pipeline
- recruiter stage/rating/notes and dashboard metrics

## Job-data coverage

ApplyAI combines dedicated provider adapters, ATS fingerprinting and bounded structured career-page extraction. Dedicated board ingestion remains available for Greenhouse, Lever and Ashby, while the discovery layer identifies Workday, SmartRecruiters, Workable, iCIMS, Oracle and SuccessFactors and can safely import public structured job pages using robots, redirect, response-size and SSRF controls. Provider-specific credentials or undocumented anti-bot bypasses are not required to call this source complete.

## Engagement

- saved searches
- job alerts
- interview reminders
- recruiter follow-ups
- notification preferences and inbox
- operator/scheduled dispatcher endpoint

Real email/push delivery providers are deployment integrations; durable platform events and preferences are source complete.

## Billing

- Free / Pro / Team entitlements
- subscription and usage persistence
- Stripe Checkout adapter
- Stripe Billing Portal adapter
- signed Stripe webhook processing
- billing ledger

Stripe account IDs, price IDs and secrets remain deployment configuration.

## Privacy

- machine-readable account export
- application-side data deletion
- anonymized audit tombstone where referential integrity must remain
- deleted-identity hash prevents silent recreation from the same external identity

Clerk account deletion itself remains an external identity-provider action.

## Operations

- internal platform metrics
- employer verification/suspension
- engagement dispatch
- source quality/health and AI quality endpoints
- golden AI evaluation
- server-only operator web console protected by operator allowlist + internal token

## Mobile and browser extension

- Expo/React Native candidate mobile source for Matches, Jobs, Applications, Alerts and Profile
- Clerk secure authentication and bearer-token API access
- Manifest V3 browser extension that hands the active public job URL to ApplyAI's safe import workflow

App-store signing, mobile store publication and extension-store publication are distribution/deployment activities.

## Deployment-only gates

The only work intentionally excluded from source-complete status is real environment activation and external provider/account evidence, including:

- AWS/Vercel/Clerk staging and production deployment
- DNS/ACM/OIDC/account configuration
- live OpenAI execution and measured cloud telemetry
- live Stripe checkout/webhook acceptance
- mobile signing/App Store/Play Store release
- extension store publication
- real email/push provider delivery
- production backup/restore and failure drills

These gates must be proven with real resources and must never be fabricated from repository source.
