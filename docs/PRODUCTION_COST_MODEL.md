# ApplyAI production cost model

This document describes cost **drivers**, not a fabricated monthly bill. Provider pricing,
free-tier limits and usage allowances can change and must be rechecked at release time.

## Vercel

Primary drivers:

- Next.js and Python function execution duration
- invocation volume
- data transfer
- image optimization if used
- build minutes
- durable queue/workflow usage if selected
- browser automation if an external browser runtime becomes necessary

Cost control:

- keep request handlers bounded
- run ingestion/AI work asynchronously
- preserve deterministic AI where a model call is unnecessary
- avoid always-on compute unless browser automation proves it is required
- retain scale benchmarks as a performance/cost regression gate

## Supabase

Primary drivers:

- Postgres compute/plan
- database size and backups
- Auth monthly active users
- Storage bytes
- Storage egress/operations
- Realtime if enabled
- Edge Function/Cron usage if selected

Cost control:

- one canonical PostgreSQL database
- reuse the existing indexed query model and durable PostgreSQL queue
- private Storage only for real candidate objects
- avoid duplicating resume blobs in both Postgres and Storage after migration
- do not enable Realtime unless a product feature uses it

The connected Supabase account currently cannot create a third active Free project. That is an
account-capacity constraint, not an application requirement. Production activation must either
make an authorized project slot available or use an appropriate paid project allocation.

## Authentication

Supabase Auth replaces Clerk as the target identity provider, reducing one independent vendor and
eliminating the need to synchronize Clerk keys/JWKS across Vercel and the API.

## AI

AI spend is driven by:

- provider/model
- input/output tokens
- job/resume enrichment frequency
- agent retries
- batch sizes

The deterministic provider remains the zero-external-AI-cost baseline. OpenAI is enabled only when
a reviewed server-side key and workload require it.

## Launch principle

Do not introduce Stripe, a paid observability vendor, another queue, or always-on compute simply
because an integration exists. Add a paid service only when a verified product requirement cannot
be met reliably by the Vercel + Supabase architecture.
