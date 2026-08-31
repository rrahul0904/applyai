# ApplyAI Production Release Checklist

Updated: 2026-08-31

Use this checklist for the first lean production launch. A checked source-code item does not substitute for a live-provider acceptance item.

## GitHub / release source

- [ ] PR #27 targets `main` and contains only lean-production changes.
- [ ] PR #27 exact-head ApplyAI CI is green.
- [ ] Lean Production Validation is green.
- [ ] Local Clean-room Certification is green.
- [ ] Open Jobs live-source acceptance is green.
- [ ] Job Search Scale Benchmark is green.
- [ ] Job Supply Scheduler Scale Benchmark is green.
- [ ] AWS Terraform and bootstrap validation remain green.
- [ ] No secret or `.env` value is committed.

## Railway PostgreSQL

- [ ] Dedicated `applyai` Railway project exists.
- [ ] Exactly one canonical production PostgreSQL database exists.
- [ ] `DATABASE_URL` is configured server-side.
- [ ] `alembic upgrade head` passes against production.
- [ ] `alembic current` matches repository head.
- [ ] `alembic check` reports zero drift.
- [ ] `postgres_tasks` exists with the expected indexes/constraints.
- [ ] Provider backup/restore capability is documented.

## Railway API

- [ ] `applyai-api` deploys from the intended release SHA.
- [ ] `APP_ENV=production`.
- [ ] `DEPLOYMENT_PROFILE=lean`.
- [ ] `TASK_QUEUE_PROVIDER=postgres`.
- [ ] No AWS credential is required to start.
- [ ] `/health` returns healthy.
- [ ] `/ready` returns healthy only when PostgreSQL is reachable.
- [ ] Production CORS allows the intended Vercel origins, not wildcard authenticated CORS.

## PostgreSQL worker

- [ ] `applyai-worker` starts with `python -m app.workers.postgres`.
- [ ] Outbox materialization works.
- [ ] Two workers claim distinct tasks safely.
- [ ] Lease expiry/recovery works.
- [ ] Retry/backoff works.
- [ ] Dead tasks are visible.
- [ ] Cancellation works.
- [ ] Unknown task types fail closed and visibly.
- [ ] Resume task routing works.
- [ ] Source task routing works.
- [ ] AI task routing works when AI provider is enabled.
- [ ] Agent task routing works where enabled.

## Cloudflare R2

- [ ] Dedicated `applyai-resumes` bucket exists.
- [ ] Bucket is private.
- [ ] R2 credentials are server-side only.
- [ ] `S3_SERVER_SIDE_ENCRYPTION=none` for R2.
- [ ] Live R2 acceptance passes PUT/HEAD/GET/presigned PUT/DELETE.
- [ ] Synthetic résumé upload creates a private object.
- [ ] Public résumé share does not reveal object key or permanent R2 URL.
- [ ] Candidate deletion removes owned object when required.

## Clerk

- [ ] Dedicated ApplyAI Clerk environment/app selected.
- [ ] Vercel has the publishable key and server-side secret.
- [ ] Railway has issuer/JWKS configuration.
- [ ] New candidate signup works.
- [ ] FastAPI verifies the real Clerk JWT.
- [ ] `/me` resolves the canonical ApplyAI user.
- [ ] Logout/login returns to the same candidate workspace.
- [ ] A second candidate cannot read the first candidate's private resources.

## Vercel Preview

- [ ] Dedicated Vercel project is named `applyai`.
- [ ] Team is `rrahul0904-5013s-projects`.
- [ ] Project root is `apps/web`.
- [ ] `APPLYAI_API_URL` points to the Railway HTTPS API.
- [ ] Clerk keys are configured in the correct environment.
- [ ] Preview deployment succeeds.
- [ ] `/`, `/sign-in`, `/sign-up`, `/onboarding`, `/dashboard`, `/jobs`, `/resume`, `/applications`, and `/settings` are healthy.
- [ ] No unexplained hydration or browser-console error exists.
- [ ] Desktop and mobile layouts are usable.

## Real job supply

- [ ] Open Jobs is registered against the real database.
- [ ] Initial ingestion runs only a bounded 1–5 groups.
- [ ] Counts for fetched/valid/invalid/created/updated/unchanged/deduplicated/failed are recorded.
- [ ] Canonical jobs preserve employer identity.
- [ ] Open Jobs remains lower authority than employer-origin ATS observations.
- [ ] No dev seed jobs are counted as production supply.
- [ ] `pnpm job-supply:initial-acceptance` passes.
- [ ] Safe ramp reaches at least 100 real canonical jobs when provider/data health permits.
- [ ] Mature `pnpm job-supply:acceptance` remains unchanged.

## Preview candidate acceptance

Use a synthetic test candidate and synthetic résumé.

- [ ] Signup.
- [ ] Onboarding.
- [ ] Private résumé upload.
- [ ] Postgres task creation.
- [ ] Railway résumé processing.
- [ ] Candidate résumé review.
- [ ] Career target/preferences.
- [ ] First-value dashboard.
- [ ] Real job inventory.
- [ ] Real job detail.
- [ ] Career Intelligence.
- [ ] Recruiter Lens.
- [ ] Application workspace.
- [ ] Role-specific résumé/application preparation.
- [ ] Interview preparation.
- [ ] Tracked résumé share.
- [ ] Separate-session engagement event.
- [ ] Resume Share analytics visible to owner.
- [ ] Logout/login persistence.

## Trust / safety

- [ ] No hiring-probability language is introduced.
- [ ] Recruiter Lens remains candidate-side self-assessment.
- [ ] AI artifacts are evidence-bound.
- [ ] No candidate evidence fabrication.
- [ ] Resume Share stores no raw IP or cross-link fingerprint.
- [ ] Return-view notification is bounded and not emitted on every refresh.
- [ ] Browser automation stops for CAPTCHA/auth/anti-bot/unknown or sensitive required questions.
- [ ] Broken optional integrations are hidden or safely disabled.

## Merge and production promotion

Do not merge PR #27 until every critical Preview item above passes.

After Preview acceptance:

1. Merge PR #27 to `main`.
2. Run all final exact-main workflows.
3. Deploy compatible Railway API/worker release from the final main SHA.
4. Promote the matching Vercel deployment to Production.
5. Run Alembic migration check again.
6. Repeat the full candidate acceptance journey against Production.
7. Inspect Vercel/Railway/queue/auth/storage errors.
8. Record the public production URL, deployment IDs, final SHA, migration revision, and measured job counts.

`LIVE_PRODUCTION_VERIFIED` is allowed only after the real production journey passes.
