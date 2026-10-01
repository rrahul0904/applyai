# ApplyAI production deployment architecture

Updated: 2026-10-01

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

The current observed production probe is HTTP 503 with
`production_ready=false` and `operator_configured=false`. No exact deployed web,
API, or worker SHA is exposed by the readiness response. Do not promote until
the owner actions in `artifacts/release/HOSTED_DEPLOYMENT_HANDOFF.md` are
complete and recorded against the release SHA.

## Alternate and historical profiles

`docs/RAILWAY_DEPLOYMENT.md` and older sections of `docs/deployment/VERCEL.md`
describe a Railway API/PostgreSQL/worker plus Clerk/R2 launch profile. That is a
separate, older deployment path; it is not the current Vercel + Supabase
workflow contract. Do not combine secrets or services from both profiles in a
single release. Any future change back to Railway must update the deployment
workflows, readiness contract, and this document together.

AWS ECS/Fargate and SQS remain an optional scale profile. They are not required
for the repository's current Vercel + Supabase launch path.
