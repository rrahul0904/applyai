# ApplyAI hosted deployment handoff

**Readiness: NO. Do not promote to production yet.** This handoff is based on release code SHA `0c77ba0af4329956782e84fdda933889d1565974` and repository deployment workflows inspected on 2026-10-01. The observed production endpoint `https://applyai-gold.vercel.app/api/readiness` returned HTTP 503 with `production_ready=false` and `operator_configured=false`. No deployment credentials, GitHub governance access, tracker access, or human UAT evidence were available in this session.

## Deployment target

Use the repository's current guarded path: **Vercel for Next.js and FastAPI, Supabase for PostgreSQL, Auth, and private Storage**. The public web app already runs at a Vercel hostname, and the repo contains separate guarded workflows for `apps/web` and `services/api`. No additional host is needed for this path.

The older Railway + Clerk + R2 instructions conflict with current `deploy-vercel-applyai*` and `production-provider-readiness` workflows. The repository docs now mark Railway/Clerk as historical/alternate. Do not combine the two profiles. The API workflow configures PostgreSQL-backed, request-triggered tasks; its readiness flag confirms configuration, not a separately running worker or successful task processing.

## Owner actions, in order

1. **Release source and governance — GitHub repository admin.** Push `codex/applyai-release-mission`, open a PR to `main`, and require PR review, disable force-push and branch deletion, then require the applicable `ApplyAI CI` checks (Web lint, Web typecheck, Web tests, Web build, API tests), `GitHub Workflow Validation`, and `ApplyAI Launch Security`. Run CI on the resulting exact PR head. The observed repo had `main` unprotected and no rulesets; this cannot be changed from the current session.

2. **Hosted secrets — GitHub Actions/Vercel/Supabase admins.** Put values in the GitHub `preview` and `production` environments; do not send secret values in chat or commit them. The guarded web workflow reads `VERCEL_TOKEN`, `APPLYAI_VERCEL_API_URL`, `APPLYAI_SUPABASE_URL`, and `APPLYAI_SUPABASE_PUBLISHABLE_KEY`. The guarded API workflow reads `VERCEL_TOKEN`, `APPLYAI_SUPABASE_DATABASE_URL`, `APPLYAI_SUPABASE_URL`, `APPLYAI_SUPABASE_S3_ACCESS_KEY_ID`, `APPLYAI_SUPABASE_S3_SECRET_ACCESS_KEY`, and `APPLYAI_WORKER_DRAIN_SECRET` (at least 24 characters). The production auth-acceptance workflow additionally reads `APPLYAI_SUPABASE_SECRET_KEY` and `APPLYAI_PRODUCTION_OPERATOR_EMAIL`. Use environment-specific values and least-privilege credentials.

3. **Real operator account — ApplyAI production operator.** Sign in to the production Supabase-backed app using the intended operator account and visit an authenticated candidate route so the account is linked to an ApplyAI user. Then run `services/api/scripts/bootstrap_operator.py` in the authorized production API environment for that existing account, granting only the needed `operator` or `admin` role. Follow [`SUPABASE_OPERATOR_BOOTSTRAP.md`](SUPABASE_OPERATOR_BOOTSTRAP.md); do not insert a placeholder role. This is required to clear `operator_configured=false`.

4. **Hosted Preview — release owner.** Dispatch **Deploy ApplyAI API to Vercel** with `target=preview` for the reviewed PR head. Set the Preview `APPLYAI_VERCEL_API_URL` to that API URL, then dispatch **Deploy ApplyAI Web to Vercel** with `target=preview`. Require the workflow health/readiness probes to pass, verify the browser-to-API Supabase-auth path and private-storage access, and confirm task execution with a real synthetic task receipt. This is hosted Preview verification, not local or simulated readiness.

5. **Human candidate UAT — five distinct participants.** Run the sessions in [`artifacts/release/HUMAN_UAT_PLAN.md`](../artifacts/release/HUMAN_UAT_PLAN.md) on the same exact SHA: desktop, mobile, keyboard/accessibility, onboarding, resume, jobs/Radar, tailoring, application handoff/tracking, interview privacy, settings, and sign-out. Record actual outcomes and redacted evidence; automated tests do not satisfy this gate.

6. **Production promotion — release owner.** After Preview, governance, operator, and UAT gates pass, merge the reviewed PR. From protected `main`, deploy the API, then web using the guarded production workflows. The workflow must observe `/api/readiness` HTTP 200 with `production_ready=true`, `operator_configured=true`, matching Supabase project, private storage configured, PostgreSQL task configuration present, and dev auth disabled. Run **Production Supabase Auth Acceptance** and **Production Provider Readiness**; verify candidate and operator journeys, task execution, logs, and exact Vercel deployment SHAs. Record web and API SHAs in the evidence ledger. Do not claim a separate long-running worker unless one is actually deployed and its health/processing is evidenced.

7. **Tracker reconciliation — tracker owner.** Provide authorized access to `/admin/reverse-engineering`, reconcile the existing donor rows and ID collisions using `artifacts/audit/tracker-patch.json`, and attach the exact PR/head/evidence. The prior tracker API request returned 401; IDs left unknown in the patch must be resolved from the live registry before any edit.

## Gate to change readiness to YES

All of the following need evidence on one release SHA: required GitHub checks and protected `main`; successful hosted Preview; operator role and production readiness HTTP 200; five completed human UAT sessions; production web and API deployments with recorded matching SHA; successful Supabase auth/provider acceptance; and tracker reconciliation. Until then the answer remains **NO — blocked on owner-controlled credentials, permissions, and human actions**.

Repository implementation and local automated checks are already recorded in [`APPLYAI_RELEASE_EVIDENCE.md`](../artifacts/release/APPLYAI_RELEASE_EVIDENCE.md) and [`applyai-evidence-ledger.json`](../artifacts/release/applyai-evidence-ledger.json). They establish repository verification only.
