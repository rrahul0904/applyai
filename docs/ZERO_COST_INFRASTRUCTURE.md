# ApplyAI zero-cost infrastructure

Status date: 2026-09-01
Release vehicle: PR #27, `agent/lean-production-wave-1`
Public validation URL: <https://applyai-preview.vercel.app>

This is a non-commercial pilot/private-beta architecture. The release gate is a projected required
infrastructure bill of exactly `$0.00/month`. Availability is intentionally sacrificed before any
provider is allowed to generate a charge.

## Approved architecture

| Capability | Provider/runtime | Required monthly cost | Cost control |
| --- | --- | ---: | --- |
| Web | Vercel Hobby, Next.js, `apps/web` | $0.00 | Non-commercial validation only; `*.vercel.app`; no paid add-ons |
| Authentication | Clerk Hobby | $0.00 | Email-based auth; no SMS; operator review at 40k/45k/50k MRU |
| API | Railway Free, sleeping FastAPI service | $0.00 | Serverless sleeping; permanent Free credit; service may become unavailable before billing |
| Database | Neon Free Postgres | $0.00 | 0.5 GB/project hard free quota; 0.25 CU; scale-to-zero; compute suspends at quota |
| Resume storage | Neon Free Postgres (`database_objects`) | $0.00 | 250 MB application hard cap; 5 files and 25 MB per user |
| Background work | Request-triggered bounded Postgres queue + public GitHub Actions | $0.00 | No polling service; one task/request; bounded 10-minute scheduled job |
| Job ingestion | Bounded GitHub Actions execution | $0.00 | Public repo, standard Ubuntu runner, small incremental batches |
| Mandatory AI | Deterministic provider | $0.00 | `AI_PROVIDER=deterministic`; no required OpenAI key |
| Monitoring | Provider logs + structured application logs + GitHub Actions | $0.00 | No paid telemetry vendor |
| Email | Clerk authentication email + in-app notifications | $0.00 | No paid email provider |
| Domain | Vercel-provided `applyai-preview.vercel.app` | $0.00 | No domain purchase |
| Commerce | Disabled | $0.00 | `BILLING_ENABLED=false`; checkout and upgrade UI hidden |

## Provider audit

### Vercel

- Plan: Hobby (`$0/month`), verified from the team API.
- Base cost: `$0.00`.
- Payment method required: no for Hobby.
- Auto-upgrade: no.
- Paid overage: Hobby usage is capped rather than automatically converted to Pro.
- Policy limitation: Hobby is for personal/non-commercial use. ApplyAI is therefore described as a
  pilot/demo/private beta, not a commercial production launch. Stripe and paid subscriptions are
  disabled.
- Current project: `applyai`; root `apps/web`; clean Preview alias above.
- Decision: PASS for non-commercial validation; FAIL for a paid/commercial launch.

References: <https://vercel.com/pricing>,
<https://vercel.com/docs/limits/fair-use-guidelines>.

### Clerk

- Plan: Hobby (`$0/month`), no card required.
- Free quota: 50,000 monthly retained users/application.
- Current user count observed: 2.
- Projected pilot usage: below 1,000 MRU (2% of the allowance).
- Paid features enabled: none required; SMS and paid enterprise connections are prohibited.
- Guard: structured operator warnings are required at 40,000, 45,000, and 50,000 MRU. No automatic
  plan upgrade is permitted.
- Decision: PASS.

Reference: <https://clerk.com/pricing>.

### Cloudflare R2

- Plan/bucket class: Standard. Both existing ApplyAI buckets currently contain 0 objects and 0 B.
- Free quota: 10 GB-month, 1,000,000 Class A, 10,000,000 Class B, free internet egress.
- Internal guard code (when S3/R2 is explicitly selected): 5 GB storage, 500,000 Class A, 5,000,000
  Class B, with warnings at 4 GB and 4.5 GB.
- Charge risk: R2 is usage billed above the free tier and a budget alert is not a hard cap. The
  account payment-method state could not be verified through the available scoped API.
- Decision: NOT REQUIRED / DISABLED. No R2 application credential is configured. Resume binaries
  use hard-capped Neon storage instead. The empty buckets incur `$0.00`.

Reference: <https://developers.cloudflare.com/r2/pricing/>.

### Neon Postgres

- Plan: Free, verified for organization `Rahul`; `$0/month`; no card required and no time limit.
- Project: `applyai` (`sparkling-meadow-54786528`), PostgreSQL 18, `aws-us-east-1`.
- Free quota: 0.5 GB storage/project, 100 CU-hours/project/month, 5 GB public network transfer.
- Current storage immediately after creation: about 31.6 MB platform baseline.
- Compute: fixed 0.25 CU and automatic scale-to-zero after inactivity.
- Hard behavior: exceeding the Free network/compute allowance suspends compute until reset or manual
  upgrade; no automatic upgrade is authorized.
- Application guard: resume objects stop at 250 MB, leaving room for relational data, indexes, and
  normal growth below the 0.5 GB provider limit.
- Decision: PASS once migration/connection acceptance is complete.

References: <https://neon.com/pricing>,
<https://neon.com/docs/introduction/network-transfer>.

### Railway

- Current plan: Trial, which automatically reverts to permanent Free rather than a paid plan.
- Permanent plan model: `$0/month` plus `$1/month` included resource credit.
- Measured initial topology during a partial day:
  - current usage: `$0.0430`;
  - CPU: `$0.00225`;
  - memory: `$0.04031`;
  - egress: `$0.0000065`;
  - volume: `$0.00047`.
- Finding: API + polling worker + Railway Postgres cannot remain within the permanent `$1` credit.
- Corrective action:
  - the active `applyai-worker` deployment was removed; active worker deployments = 0;
  - `applyai-api` has `sleepApplication=true`;
  - Postgres is migrating to Neon, after which the Railway Postgres service/volume must be stopped;
  - queue work is request-triggered or runs as a bounded public GitHub Actions job.
- Pre-cutover data check through the internal API: 0 users, 0 applications, 0 subscriptions,
  0 saved searches, 0 resume documents, 0 organizations, 0 sources, and 0 active jobs. There is no
  candidate data requiring transfer; the Neon cutover can apply the canonical Alembic schema from
  zero. A temporary Railway database proxy used only to validate connectivity was deleted.
- Usage limit caveat: Railway only accepts compute hard limits of exactly `$0` or `$10+`. `$10` is
  prohibited. After migration and acceptance, set `$0` if Railway's permanent Free credit does not
  itself provide a no-charge shutdown boundary.
- Decision: FAIL for the old topology; pending PASS for sleeping API-only topology after measured
  post-migration usage projects to less than the included Free credit.

References: <https://docs.railway.com/pricing/plans>,
<https://docs.railway.com/pricing/free-trial>,
<https://docs.railway.com/deployments/serverless>,
<https://docs.railway.com/pricing/cost-control>.

### GitHub Actions

- Repository: public.
- Runner: standard `ubuntu-24.04`, never a larger runner.
- Cost: standard GitHub-hosted runner minutes are free for public repositories.
- Work is bounded to 10 minutes and produces no candidate resume artifacts.
- Decision: PASS.

Reference: <https://docs.github.com/en/billing/concepts/product-billing/github-actions>.

## Application-level fail-closed controls

- Resume file size: 5 MB maximum.
- Retained resume versions: 5/user maximum.
- Resume bytes: 25 MB/user maximum.
- Required Postgres object storage: 250 MB global maximum, with warning at 80%, critical at 90%,
  and upload refusal at 100%.
- R2 (disabled fallback): 5 GB, 500k Class A, 5M Class B.
- Concurrent quota reservations use a PostgreSQL advisory transaction lock.
- Expired upload artifacts are deleted by bounded maintenance.
- Paid billing API and UI are disabled.
- Mandatory AI is deterministic.
- Continuous browser automation, continuous crawling, Redis, Kafka, paid queues, paid search, and
  paid observability are not part of the launch path.

## Zero-cost acceptance

| Provider | Projected amount due | Gate |
| --- | ---: | --- |
| Vercel | $0.00 | PASS for non-commercial validation |
| Clerk | $0.00 | PASS |
| Neon | $0.00 | PENDING migration acceptance |
| Railway | $0.00 | PENDING API-only measurement and Postgres shutdown |
| GitHub Actions | $0.00 | PASS |
| Cloudflare R2 | $0.00 (unused) | PASS as non-required/disabled |
| OpenAI | $0.00 (unused) | PASS |
| Email | $0.00 | PASS |
| Domain | $0.00 | PASS |

Do not merge or promote Production while any row is pending or failed.
