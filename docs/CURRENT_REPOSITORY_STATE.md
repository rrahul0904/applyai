# Current Repository State

Updated: 2026-08-07

## Source control

- Repository: `rrahul0904/applyai`
- Default branch: `main`
- Platform-completion branch: `agent/platform-completion`
- Pull request: #14
- Architecture: Next.js App Router + Clerk web; Expo/React Native mobile; FastAPI modular monolith; PostgreSQL/Alembic; private S3; dedicated resume/source/AI SQS queues; Vercel web + AWS ECS/Aurora target.
- Browser extension: Manifest V3 public-job URL handoff into the same safe server-side import pipeline.
- No Redis, Kafka, Kubernetes, or premature microservice split was introduced solely to satisfy platform breadth.

This repository now has a source-complete platform boundary. Real external deployment, provider credentials, cloud measurements, signing and store publication are tracked separately and are never inferred from source code.

## Candidate product

Canonical authenticated candidate routes include:

```text
/dashboard
/matches
/jobs
/jobs/[id]
/saved
/applications
/applications/[id]
/resume
/resume/studio
/career
/interview/[jobId]
/network
/analytics
/alerts
/profile
/billing
/settings
/import-job
```

Historical `/demo` and `/beta` routes redirect into the canonical candidate product instead of maintaining parallel state or APIs.

Implemented candidate capabilities:

- identity mapping and owner-scoped APIs;
- onboarding, profile, experience, education, skills, goals and preferences;
- durable private resume upload/processing/version history;
- Resume Studio with job-specific editable variants and export;
- PostgreSQL job search/filter/cursor pagination;
- saved jobs and saved-search alerts;
- application command center with status/events/notes;
- candidate-approved first-party submission and third-party external handoff;
- Career Memory;
- AI Matches;
- Career Intelligence resume/application/interview copilots;
- interview practice sessions and feedback;
- recruiter/hiring-manager/referral contacts and follow-ups;
- notifications and reminder inbox;
- candidate analytics;
- company intelligence derived from known posting evidence;
- subscription/entitlement visibility;
- account export and application-side deletion.

## Career Intelligence

Career Intelligence V1 remains the deterministic explainable baseline. Career Intelligence V2 is the first-class durable AI domain.

```text
verified profile/resume/Career Memory
          +
canonical job/source evidence
          +
deterministic match factors
          |
          v
server evidence catalog
          |
          v
AIJobRun + transactional outbox
          |
          v
AI SQS -> AI worker -> provider
          |
          v
strict schema + evidence validation
          |
          v
versioned domain artifacts
          |
          v
candidate review + quality feedback
```

Implemented task families:

- deep job match;
- resume tailoring;
- application copilot;
- interview preparation.

Provider boundary:

- deterministic evidence-safe provider for local/CI;
- structured OpenAI provider for reviewed deployment environments;
- deterministic local semantic embedding provider for CI;
- optional server-side OpenAI embedding provider;
- strict JSON/Pydantic validation;
- exact evidence-reference checks;
- versioned prompt/model/schema metadata;
- latency/token/configured-cost telemetry;
- transient retry vs terminal schema/evidence failure behavior.

Evaluation includes a source-controlled golden dataset, Precision@5/10, reciprocal rank, evidence support rate, unsupported-reference count and operator baseline-vs-candidate comparison.

## Resume and application workflow

Resume processing remains evidence/provenance driven. Resume Studio adds candidate-owned editable variants without replacing the durable master-resume/version history.

Application submission has an explicit safety boundary:

- the candidate must approve a submission request;
- verified first-party ApplyAI employer jobs can receive the approved application directly;
- third-party jobs produce an external handoff to the employer's public application page;
- ApplyAI does not bypass employer login, CAPTCHA, anti-bot controls or private application endpoints.

## Employer/recruiter platform

Implemented:

- employer organizations;
- role-based organization membership;
- operator trust verification/suspension;
- job draft/edit/publish/close;
- published first-party roles enter the same canonical candidate job index;
- first-party ApplyAI submissions create employer applicants;
- candidate pipeline stages, ratings and notes;
- employer dashboard metrics.

The employer and candidate products share the same canonical jobs/applications rather than maintaining demo-only copies.

## Billing and entitlements

Implemented source:

- Free / Pro / Team entitlement definitions;
- subscription and usage persistence;
- Stripe Checkout adapter;
- Stripe Billing Portal adapter;
- signed Stripe webhook verification and lifecycle updates;
- billing ledger;
- public pricing and authenticated billing UI.

Live Stripe account values are deployment configuration.

## Job-data platform

Implemented:

- Greenhouse, Lever and Ashby dedicated adapters;
- generic structured public-career-page import;
- ATS detection for Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, iCIMS, Oracle and SuccessFactors;
- robots/redirect/SSRF/response-size constrained discovery;
- source registry, leasing, durable dispatch and workers;
- raw provenance retention;
- canonical authority/dedup/conflict resolution;
- freshness and closure evidence;
- apply-URL verification;
- protected source quality metrics;
- 10K/50K/250K synthetic PostgreSQL benchmark gate.

No login bypass, proxy rotation, CAPTCHA solving or private endpoint access is used to claim source coverage.

## Notifications and engagement

Implemented durable state includes:

- saved searches;
- job alerts;
- notification preferences;
- notification inbox/read state;
- interview reminders;
- recruiter follow-ups;
- engagement dispatcher.

A real email/push provider remains an external deployment integration.

## Privacy/account lifecycle

Implemented:

- machine-readable candidate data export;
- application-side personal-data deletion;
- anonymized user tombstone when an immutable/audit foreign key must remain valid;
- hashed deleted-identity record preventing the same external identity from silently recreating the deleted ApplyAI account.

Deleting the external Clerk identity itself is an identity-provider operation.

## Operator platform

The internal platform has protected endpoints and a server-only web console for:

- platform counters;
- employer verification/suspension;
- engagement dispatch;
- source quality/health;
- AI runtime quality;
- golden AI evaluation.

The internal token is never exposed as a browser/public environment variable.

## Native mobile

`/mobile` contains the Expo/React Native candidate client using Clerk authentication and the same FastAPI contract as web.

Native source includes:

- AI Matches;
- Jobs;
- Applications;
- Alerts;
- Profile/Career Memory summary.

Repository tests transpile the native TS/TSX source. Signing credentials, native release builds and store publication are external distribution/deployment work.

## Browser extension

`/apps/extension` contains a Manifest V3 extension with only:

```text
activeTab
storage
```

It hands the active public job URL to `/import-job`. The existing server-side safe importer remains authoritative. Repository tests validate extension permissions and JavaScript syntax.

## Infrastructure source

AWS staging source contains:

```text
VPC / two AZs
HTTPS ALB
private ECS/Fargate
Aurora PostgreSQL Serverless v2
ECR
private encrypted/versioned resume S3
resume SQS + DLQ
source SQS + DLQ
AI SQS + DLQ
resume/source/AI workers
queue-aware outbox publishers
source dispatcher / EventBridge
migration task
least-privilege IAM
CloudWatch logs and alarms
```

Bootstrap, preflight, infrastructure, release, rollback and verification workflows are source controlled. The reviewed model secret is scoped to the AI runtime rather than broadly exposed to the API/web.

## Repository validation

The platform completion gate covers:

```text
Web lint
Web typecheck
Web unit tests
native-mobile source transpilation
browser-extension source checks
Next.js production build
API tests
Alembic zero-to-head and metadata drift
OpenAPI generated-client drift
API Docker image build
Terraform validation
Candidate Playwright browser journey
Demo capture
CloudFormation bootstrap validation
GitHub workflow validation
10K / 50K / 250K PostgreSQL job-search benchmarks
```

Exact-head evidence is required after every source-changing commit.

## External environment gates

The remaining work is exclusively real deployment/runtime/distribution evidence:

```text
AWS/Vercel/Clerk staging activation
real S3/SQS/ECS/Aurora candidate acceptance
real ATS/provider throughput/freshness/cost acceptance
live OpenAI model and embedding acceptance
live Stripe checkout/webhook acceptance
real email/push provider delivery
production promotion and measured backup/restore/failure drills
Apple/Google signing + App Store/Play Store publication
browser-extension store publication
external Clerk identity deletion/revocation
```

These remain `BLOCKED` until real accounts, credentials and infrastructure exist. No repository-only change can honestly mark them complete.
