# ApplyAI hosted deployment handoff

**Production readiness: NO.** PR #80 (`codex/applyai-release-mission`) is at SHA `3515e522264c18cc7a21eebc7e954a620461cc55`; all current hosted CI checks and its Vercel Preview passed. The preview is a real hosted deployment, but it does not close the production or human gates below.

## Observed hosted state

- **Vercel project:** `applyai` in team `rrahul0904-5013s-projects`, connected to `rrahul0904/applyai`. The Vercel GitHub integration created the PR Preview for SHA `3515e522264c18cc7a21eebc7e954a620461cc55`; deployment status is **success** at [the Preview URL](https://applyai-nun4i4v1y-rrahul0904-5013s-projects.vercel.app). `/` and `/sign-in` return HTTP 200. `/api/readiness` returns HTTP 200, `runtime_ready=true`, but `production_ready=false` because `operator_configured=false`. API, database, storage, background-task configuration, Supabase Auth and instance match are true in the Preview response.
- **Production:** `https://applyai-gold.vercel.app` has a successful Vercel deployment record for main SHA `9798aa613c45cdf9d54f3e2c6c47481ca31d1852` from 2026-09-22, not the PR candidate. Current `/api/readiness` returns HTTP 503 with `runtime_ready=true`, `production_ready=false`, and `operator_configured=false`. API/database/storage/Supabase configuration flags and instance match are true; dev auth is false. The production Clerk compatibility fields report publishable mode `test` and secret mode `unknown`; Supabase is the reported active auth provider.
- **Vercel inspection access:** no Vercel CLI, local Vercel login, Vercel token in the local process, or open browser session was available. The GitHub Vercel integration provided the project/deployment records and deployment URLs, but Vercel dashboard build logs and Vercel-side secret names could not be inspected directly. Never infer secret values from readiness flags.
- **GitHub deployment secrets:** the repository-level Actions inventory contains only `APPLYAI_DATABASE_URL`, `CLERK_ISSUER`, and `CLERK_JWKS_URL`. The `preview` and `production` environment secret inventories are empty; no Vercel/Supabase deployment secret names are configured in those GitHub environments. This does not imply the Vercel project has no environment values: its hosted Preview readiness proves the required API/Supabase configuration is present there. The guarded GitHub deployment workflows still lack their required GitHub secrets.
- **Branch governance:** resolved. GitHub's classic branch-protection API now confirms `main` requires PR review (one approval; stale reviews dismissed; last push approval required), up-to-date required branches, 21 exact checks, admin enforcement, no force-push, and no deletion. The PR remains draft and requires a reviewer; no bypass is enabled for admins. An emergency would require an audited, temporary policy change by a repository admin followed by immediate restoration and verification.
- **Production identity:** no real ApplyAI operator row is configured. An intended operator must first authenticate in production and link the real account, then the authorized production operator must follow `docs/SUPABASE_OPERATOR_BOOTSTRAP.md`. Do not create a placeholder role.
- **Human UAT:** 0/5 human sessions completed. The prepared session plan remains in `artifacts/release/HUMAN_UAT_PLAN.md`; automated Chromium tests do not count as human UAT.
- **Real inventory and external providers:** functional CI explicitly sets `REQUIRE_REAL_INVENTORY=0`. It records the 2,000,000 eligible real-job threshold as `EXTERNAL_GATE_NOT_EXECUTED`; seeded fixture jobs and synthetic scale benchmarks are not live inventory. The bounded job-catalog seed check was skipped. No live external Job Radar provider or production ingestion receipt was verified.
- **Tracker:** direct tracker access returned 401. Do not mutate donor rows until an authorized live registry session is available and canonical IDs have been checked.

## CI evidence on the current PR head

PR #80 is open as a draft. Hosted runs all target `3515e522264c18cc7a21eebc7e954a620461cc55`:

- [ApplyAI CI](https://github.com/rrahul0904/applyai/actions/runs/36910276670) — pass, including API tests/migrations/container, web tests/typecheck/build, Playwright, OpenAPI drift and Terraform validation.
- [ApplyAI Launch Security](https://github.com/rrahul0904/applyai/actions/runs/36910276828) — pass, including dependency audits, API security regressions, SAST and secret-pattern checks.
- [ApplyAI Full Functional Certification](https://github.com/rrahul0904/applyai/actions/runs/36910276592) — pass; the strict real-inventory gate was intentionally not run because `REQUIRE_REAL_INVENTORY=0`.
- [ApplyAI Local Clean-room Certification](https://github.com/rrahul0904/applyai/actions/runs/36910276844) — pass in hosted CI.
- [Vercel Preview status](https://vercel.com/rrahul0904-5013s-projects/applyai/4jCpG848aRYg5zp4nTFvDfv7GJeX) — deployment completed.
- Candidate Playwright ran 11 tests and skipped 5. It seeded 144 deterministic jobs and used development auth, local object storage and an in-memory queue. Accessibility and responsive/keyboard browser tests passed; real Clerk/Supabase candidate and operator acceptance tests skipped because production credentials were not available.

## Remaining owner actions

1. Obtain the required second-person PR review and make sure all required checks pass on the final exact PR head. `main` protection is already configured and verified.
2. Add the guarded-deployment secrets to the GitHub `preview` and `production` environments. Web workflow names: `VERCEL_TOKEN`, `APPLYAI_VERCEL_API_URL`, `APPLYAI_SUPABASE_URL`, `APPLYAI_SUPABASE_PUBLISHABLE_KEY`. API workflow names: `VERCEL_TOKEN`, `APPLYAI_SUPABASE_DATABASE_URL`, `APPLYAI_SUPABASE_URL`, `APPLYAI_SUPABASE_S3_ACCESS_KEY_ID`, `APPLYAI_SUPABASE_S3_SECRET_ACCESS_KEY`, `APPLYAI_WORKER_DRAIN_SECRET` (at least 24 characters). Production auth acceptance also requires `APPLYAI_SUPABASE_SECRET_KEY` and `APPLYAI_PRODUCTION_OPERATOR_EMAIL`. Store values only in the approved secret manager/GitHub environment; do not send them in chat.
3. Create/link the real intended operator through the production Supabase flow, then run the documented operator bootstrap against that real account. Reprobe until production readiness returns HTTP 200 and `production_ready=true`.
4. Conduct five distinct human candidate UAT sessions on one frozen SHA, using the prepared plan and redacted evidence. Include desktop, mobile, keyboard/accessibility, application handoff, interview privacy, settings and sign-out.
5. Obtain the separate real-inventory/provider acceptance required by the 2,000,000-job gate, and verify real authenticated task execution plus private resume-storage upload/processing receipts. Current CI uses seeded data, development identity, local storage and memory tasks for its candidate E2E journey.
6. After all gates pass, promote the reviewed exact SHA through the guarded Vercel API and web workflows. Verify the production deployment SHA and post-deploy candidate/operator journeys. The current production deployment remains on old main SHA `9798aa6…`.
7. Give the tracker owner authorized access to reconcile the prepared donor patch without guessing or overwriting IDs.

## Deployment target

The repo-native path is Vercel web + Vercel FastAPI + Supabase. Vercel is the appropriate web host here because the production hostname and connected project already exist, the PR Preview deployed from the existing GitHub connection, and the repository has guarded web/API workflows. Older Railway/Clerk/R2 documentation is marked historical; do not mix those profile variables into the current Supabase release.

Readiness remains **NO** until real operator readiness, human UAT, real inventory/provider/task/storage evidence, exact production SHA alignment and tracker access are resolved. Passing CI and a live Preview establish repository and Preview evidence only.
