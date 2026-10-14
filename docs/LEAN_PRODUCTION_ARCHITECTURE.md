# ApplyAI production deployment architecture

Updated: 2026-10-13 (live evidence observed 2026-10-14 02:12 UTC)

## Repository release target

The current production deployment workflows target Vercel for both the Next.js
web application and FastAPI API, with Supabase for PostgreSQL, Auth, and private
resume storage:

```text
Candidate
  -> Vercel / Next.js web (`apps/web`)
  -> Vercel / FastAPI (`services/api`)
  -> Supabase Auth + PostgreSQL + private Storage
  -> PostgreSQL task queue and request-triggered task processing
```

This is the repository's deployment target, not proof that the currently hosted
services run this topology or a particular commit. The production readiness
workflow checks Vercel + Supabase at `https://applyai-gold.vercel.app`.

The root `vercel.json` also declares the web and API services for Vercel multi-service deployment. The per-service GitHub workflows remain in the repository; their existence does not certify that a hosted project is currently serving the exact source SHA.

The corresponding guarded workflows are:

- `.github/workflows/deploy-vercel-applyai.yml` — Vercel web project `applyai`,
  root `apps/web`.
- `.github/workflows/deploy-vercel-applyai-api.yml` — Vercel API project
  `applyai-api`, root `services/api`.
- `.github/workflows/production-provider-readiness.yml` and
  `.github/workflows/production-supabase-auth-acceptance.yml` — hosted readiness
  and authenticated production acceptance.

Production uses `AUTH_PROVIDER=supabase`, `TASK_QUEUE_PROVIDER=postgres`,
`OBJECT_STORAGE_PROVIDER=supabase`, and `REQUEST_TRIGGERED_TASKS_ENABLED=true`
as set by the API deployment workflow. This profile configures request-triggered
durable task processing; it does not prove a separate long-running worker is
deployed or processing work. The current readiness contract's
`background_worker_configured` field indicates configuration only.

## Promotion gates

Deploy only an exact, reviewed release SHA. The release sequence is Preview API,
Preview web, authenticated acceptance and human UAT, then protected-main API and
web production workflows. The production workflow requires
`production_ready=true`, a matching Supabase instance, configured operator role,
private storage configuration, disabled dev auth, and task processing
configuration. A successful HTTP status alone is insufficient.

## Observed production state (2026-10-14 02:12 UTC)

The latest observed successful Vercel Production deployment is GitHub deployment
`6992311376`, SHA `406ee1031158f5a108107df293e1100e0d0b4fcb`, branch
`release/vercel-services`, URL
`https://applyai-i07405rc8-rrahul0904-5013s-projects.vercel.app`. The configured
production domain `https://applyai-gold.vercel.app/api/readiness` returned HTTP
503. Its body reported `runtime_ready=false`, `production_ready=false`,
`database_reachable=false`, `storage_configured=false`,
`background_worker_configured=false`, `supabase_instance_match=false`, and
`operator_configured=false`. It reported the API as reachable, but the direct
`https://applyai-api.vercel.app/ready` probe returned HTTP 503 with `NOT_READY`.
This is an observed disagreement in the deployed readiness contract, not proof
that the API is healthy. The API deployment SHA, migration head, and any worker
version are not exposed by these endpoints.

The readiness contract change in this integration checkout validates the API
payload and records the upstream HTTP status. It has not yet been deployed or
verified against production. Do not promote until database, storage, auth,
operator and task-processing checks are healthy on one exact reviewed release
SHA, and the owner actions in `artifacts/release/HOSTED_DEPLOYMENT_HANDOFF.md`
are complete and recorded.

## Alternate and historical profiles

`docs/RAILWAY_DEPLOYMENT.md` and older sections of `docs/deployment/VERCEL.md`
describe a Railway API/PostgreSQL/worker plus Clerk/R2 launch profile. That is a
separate, older deployment path; it is not the current Vercel + Supabase
workflow contract. Do not combine secrets or services from both profiles in a
single release. Any future change back to Railway must update the deployment
workflows, readiness contract, and this document together.

AWS ECS/Fargate and SQS remain an optional scale profile. They are not required
for the repository's current Vercel + Supabase launch path.
