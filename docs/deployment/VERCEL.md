# ApplyAI Web on Vercel

Updated: 2026-08-31

## Deployment model

Vercel hosts the **Next.js web application only**.

The lean production backend is:

```text
Railway / FastAPI
  -> Railway PostgreSQL
  -> Cloudflare R2
  -> TaskOutbox -> postgres_tasks -> Railway worker
```

AWS remains an optional scale profile and is not required for the launch deployment.

The Next.js application proxies authenticated browser requests through `/api/backend/*` to `APPLYAI_API_URL`, so browser code never needs database, R2 or backend provider credentials.

## Vercel project

Use one dedicated Vercel project:

- Project name: `applyai`
- Team: `rrahul0904-5013s-projects`
- Git repository: `rrahul0904/applyai`
- Framework: Next.js
- Root directory: `apps/web`
- Install command: `cd ../.. && pnpm install --frozen-lockfile`
- Build command: `pnpm build`

Do not attach ApplyAI to SkillForge, ThreadTales, Provenance Cleaner or another existing Vercel project.

## Required Vercel environment variables

Set these for Preview and Production with environment-appropriate values:

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
APPLYAI_API_URL
APP_ENV=production
DEV_AUTH_ENABLED=false
```

`APPLYAI_API_URL` must be the real Railway FastAPI HTTPS endpoint for the lean launch.

Optional operator/admin functionality may also require:

```text
APPLYAI_OPERATOR_EMAILS
INTERNAL_API_TOKEN
```

Never expose `CLERK_SECRET_KEY`, `INTERNAL_API_TOKEN`, database credentials, R2 credentials or Vercel tokens as `NEXT_PUBLIC_*` variables.

## GitHub Actions secrets

The guarded deployment workflow expects:

```text
VERCEL_TOKEN
APPLYAI_VERCEL_API_URL
APPLYAI_VERCEL_CLERK_PUBLISHABLE_KEY
APPLYAI_VERCEL_CLERK_SECRET_KEY
```

Optional:

```text
APPLYAI_VERCEL_OPERATOR_EMAILS
APPLYAI_VERCEL_INTERNAL_API_TOKEN
```

The workflow can create the dedicated `applyai` project if it does not exist, link it to `rrahul0904/applyai`, enforce the web root/build settings, synchronize target environment variables, build with Vercel and deploy the prebuilt artifact.

The branch push path intentionally skips deployment when required secrets are absent; `workflow_dispatch` fails closed instead of reporting a fake deployment.

## Promotion policy

- `agent/lean-production-wave-1` is the final Preview release branch.
- Production deployment is allowed only from `main`.
- Do not merge PR #27 until the real Railway/R2/Clerk/Open Jobs/Vercel Preview candidate acceptance gate passes.
- After merge, run the exact-main release gate before Vercel Production promotion.

## Preview health checks

After a real Preview deployment verify:

1. `/`, `/sign-in` and `/sign-up` render;
2. Clerk authentication completes;
3. `/api/backend/me` reaches the Railway API;
4. onboarding persists to Railway PostgreSQL;
5. a synthetic résumé can be uploaded to private R2 and processed by the Railway Postgres worker;
6. real jobs load from the production-shaped database;
7. job detail renders Career Intelligence, Recruiter Lens and Career System;
8. application workspace and interview preparation are usable;
9. a Resume Share link works from a separate session and returns engagement to the owner;
10. logout/login returns to the same candidate workspace;
11. no unexplained Vercel runtime 5xx, hydration or browser-console errors exist.

## Current provider boundary

The connected Vercel team is available, but no dedicated `applyai` project currently exists. The latest deployment preflight confirmed the four required GitHub Actions values above are not configured, so all create/link/build/deploy steps were safely skipped.

A meaningful Preview also depends on the real Railway API URL and Clerk instance. Do not create an empty Vercel project merely to claim that ApplyAI is deployed.

See `DEPLOYMENT.md` and `docs/PRODUCTION_RELEASE_CHECKLIST.md` for the final launch order.
