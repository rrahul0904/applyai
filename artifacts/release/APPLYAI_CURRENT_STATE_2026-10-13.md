# ApplyAI current release state

Observed: 2026-10-14 local date; production probes returned HTTP dates 2026-10-14 02:12 UTC. Implementation code commit: `dd54eb6246a2814eb2bcc3a1b9e8ce21d8b7f2ab` on `codex/applyai-release-mission`; local full API tests pass. PR #80 evidence-tip `b2719b0efe41ad8cb85929912c8a7a9c3745dc06` has completed hosted code checks; its Vercel Preview is blocked by the project rate limit.

## Release truth

ApplyAI is not production-ready. The latest observed successful Vercel Production deployment is GitHub deployment `6992311376`, source SHA `406ee1031158f5a108107df293e1100e0d0b4fcb`, branch `release/vercel-services`, URL `https://applyai-i07405rc8-rrahul0904-5013s-projects.vercel.app`. The configured web domain is `https://applyai-gold.vercel.app`. That production SHA is not `main` and this record does not establish a protected-main release.

The latest observed integration Preview is Vercel deployment for older PR head `ed571165194185c4b89a675dd5005a2f02c904e6` (alias `https://applyai-git-codex-applyai-rele-f33155-rrahul0904-5013s-projects.vercel.app`); it is not the current candidate. The earlier inspected Preview deployment was GitHub deployment `7030380097`, source SHA `f2d12e51fca978d4ebeafb380ac7fa517b84868b`, PR #92 documentation branch, URL `https://applyai-ei37tx72f-rrahul0904-5013s-projects.vercel.app`. It does not represent the current implementation branch. The last exact PR #80 candidate head previously checked was `f4a36d0810ba67603a3eff1334aae6db1675a1a9`; it was open, non-draft, and required an independent approval. Its previous green checks do not certify subsequent source changes. The locally tested candidate `d9530a632af91fe3a7608240644bb42a20174c95` includes a follow-up patch for the three high-severity web dependency findings surfaced on the earlier exact head. PR #80 remote head before the implementation push was `ed571165194185c4b89a675dd5005a2f02c904e6`; implementation code is `dd54eb6246a2814eb2bcc3a1b9e8ce21d8b7f2ab`, followed by evidence tip `b2719b0efe41ad8cb85929912c8a7a9c3745dc06`. Exact-head checks on that tip passed except the Vercel Preview deployment, which was rate limited. PR #80 remains open, non-draft, and `REVIEW_REQUIRED`.

## Live probes

At 2026-10-14 02:12 UTC, on the prior code head `ed571165194185c4b89a675dd5005a2f02c904e6`:

- `GET https://applyai-gold.vercel.app/api/readiness` returned HTTP 503. JSON reported `runtime_ready=false`, `production_ready=false`, database and storage false, worker configuration false, Supabase instance mismatch, and operator configuration false. It reported `api_reachable=true`.
- `GET https://applyai-api.vercel.app/ready` returned HTTP 503 with `NOT_READY`.
- The disagreement means the deployed readiness route does not validate the upstream health contract correctly. A fail-closed schema/status validation fix is present in the candidate source and passed exact-head hosted verification. The new candidate Preview was not deployed because Vercel returned its 24-hour rate-limit failure.
- Production API commit, Alembic head, durable worker version/health, database provider identity, real authorized source inventory, authenticated candidate identity and human UAT are not exposed by the probes and remain unverified.

## Implementation changes under verification

Commit `538c231d51c05e70b55a616457d0facdd6fb7585` fixes connector checkpoint propagation and safe advancement, preserves PartnerFeed validators on HTTP 304, distinguishes partial/inconclusive source runs from complete runs, and excludes partial coverage from accepted provider counts. It also makes the web readiness API contract fail closed on HTTP errors and malformed responses. Regression tests are included. Commit `d9530a632af91fe3a7608240644bb42a20174c95` upgrades Next.js and `eslint-config-next` to 16.3.8, and pins patched transitive `source-map-js` 1.2.2 and `sharp` 0.35.5 in workspace overrides. Commit `dd54eb6246a2814eb2bcc3a1b9e8ce21d8b7f2ab` adds browser form read-back verification before submission, a terminal API receipt guard bound to candidate-approved fields, and human-only legal-attestation handling.

## Verification status

- Web TypeScript check: passed on `d9530a632af91fe3a7608240644bb42a20174c95` as part of the production build.
- Web tests: 79 passed across 26 files, including four readiness-contract tests.
- Web production build: passed using webpack on `d9530a632af91fe3a7608240644bb42a20174c95`; Next.js route-module export issue was caught and fixed before the implementation commit.
- Production dependency audit: zero high/critical findings on the exact candidate after upgrading Next.js/eslint-config-next to 16.3.8, `source-map-js` to 1.2.2, and `sharp` to 0.35.5.
- Web lint: passed with zero errors and four existing warnings.
- Full API pytest suite: 450 passed, 1 skipped, 0 failed on exact code commit `dd54eb6246a2814eb2bcc3a1b9e8ce21d8b7f2ab` using migrated `applyai_test` at `d0v4z6s9w197`.
- Verified browser submission: 11 focused tests passed on exact code commit `dd54eb6246a2814eb2bcc3a1b9e8ce21d8b7f2ab`; no live ATS or deployed worker verification is claimed.
- Job-supply acceptance: blocked; local database has zero active real sources and zero real jobs. Reports are in `initial-job-supply-report.json` and `job-supply-report.json`.
- Local PostgreSQL migrations: `alembic upgrade head` and `alembic check` passed for both `applyai` and `applyai_test`, head `d0v4z6s9w197`.
- Authenticated customer/operator journeys, browser execution, billing, security, production ingestion, and human UAT: not verified.

## Architecture actually observed

The source-controlled target is Vercel web and API plus Supabase Auth/PostgreSQL/Storage and PostgreSQL-backed tasks (`vercel.json`, `docs/LEAN_PRODUCTION_ARCHITECTURE.md`). Production runs Vercel-hosted web/API endpoints but current service health is false. This evidence does not prove the production API deployment's exact source SHA or Supabase connectivity. A separately healthy long-running worker is not verified. Railway + Clerk + R2 are historical documentation; AWS is an optional scale profile.

## Remaining external gates

1. Restore a healthy production API/database connection and confirm migrations at `d0v4z6s9w197` or newer on the production database.
2. Configure and verify the matching Supabase project, private storage, production auth, and operator role through the owner-controlled Vercel/Supabase environments.
3. Deploy an exact reviewed SHA to Preview, verify readiness and real authorized source ingestion, then complete authenticated candidate/operator journeys and human UAT.
4. Vercel returned “Deployment rate limited — retry in 24 hours” for current PR #80 evidence tip `b2719b0efe41ad8cb85929912c8a7a9c3745dc06`. After the account limit clears, deploy and verify this candidate Preview, including readiness and browser-worker runtime.
5. Obtain the independent approval required by PR #80 branch protection before merge or production promotion.

No credentials or provider state are inferred from repository files. No release or production promotion is authorized by this evidence record.


Exact-head hosted validation on `b2719b0efe41ad8cb85929912c8a7a9c3745dc06`: all GitHub checks passed except Vercel; one bounded catalogue seed check was intentionally skipped. Browser verification contract/image, API tests/security, Playwright, fresh-clone certification, no-deploy predeploy certification, migrations, web build/tests/typecheck/lint, dependency audits, RLS, SAST, and scale checks passed. Vercel reported its 24-hour deployment rate limit. The current local evidence update records this result.
