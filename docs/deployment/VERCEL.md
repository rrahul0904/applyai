# ApplyAI Web on Vercel

## Deployment model

Vercel hosts the **Next.js web application only**.

The existing ApplyAI backend remains the canonical runtime for:

- FastAPI APIs
- PostgreSQL
- S3 resume objects
- durable resume processing
- background workers / queues
- application-agent execution
- other long-running backend services

The Next.js application proxies authenticated browser requests through `/api/backend/*` to `APPLYAI_API_URL`, so browser code never needs a public backend credential.

## Vercel project

Use one dedicated Vercel project:

- Project name: `applyai`
- Team: `rrahul0904-5013s-projects`
- Git repository: `rrahul0904/applyai`
- Framework: Next.js
- Root directory: `apps/web`
- Install command: `cd ../.. && pnpm install --frozen-lockfile`
- Build command: `pnpm build`

Do not attach ApplyAI to SkillForge, ThreadTales, or another existing Vercel project.

## Required Vercel environment variables

Set these for both Preview and Production unless a target-specific value is required:

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
APPLYAI_API_URL
APP_ENV=production
DEV_AUTH_ENABLED=false
```

Optional operator/admin functionality may also require:

```text
APPLYAI_OPERATOR_EMAILS
INTERNAL_API_TOKEN
```

Never expose `CLERK_SECRET_KEY`, `INTERNAL_API_TOKEN`, backend database credentials, AWS secrets, or Vercel tokens as `NEXT_PUBLIC_*` variables.

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

The workflow creates the `applyai` Vercel project if it does not exist, links it to `rrahul0904/applyai`, applies the web root/build settings, synchronizes the target environment variables, builds with Vercel, then deploys the prebuilt artifact.

## Promotion policy

- Feature branches deploy as **Preview**.
- Production deployment is allowed only from `main`.
- Validate the preview before promotion or a production deployment.
- Production deployment does not migrate or replace the FastAPI backend.

## Health checks

After deployment verify:

1. landing/sign-in page renders;
2. Clerk authentication completes;
3. `/api/backend/me` reaches the configured ApplyAI API;
4. jobs load;
5. a job detail page renders Career Intelligence and Career System;
6. application workspace can be created;
7. no Vercel runtime 5xx errors are present.
