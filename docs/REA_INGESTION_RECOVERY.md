# REA-guided ApplyAI ingestion recovery

## Scope and verified baseline (2026-10-13)
- Source branch: `release/vercel-services`.
- The README describes Greenhouse, Lever, Ashby, SmartRecruiters, Open Jobs, source scheduling, leasing, transactional dispatch, deduplication, freshness and closure evidence.
- `package.json` defines `pnpm job-supply:initial-acceptance` and `pnpm job-supply:acceptance`.
- Production API `/ready` and web `/api/readiness` both returned HTTP 503; database reachability is false.
- Vercel `applyai-api` lacks `DATABASE_URL`. No secrets belong in GitHub.
- This document is a certification plan, not proof that ingestion runs.

## Governed REA workflow
Use [morluto/rea](https://github.com/morluto/rea) as an evidence-discovery provider. Record target identity, allowed access, observable capabilities, provenance and uncertainty. Agent Work OS retains policy, clean-room boundaries, implementation and test authority. No private-source extraction, bypass, or copied proprietary code.

## First end-to-end ingestion certification
1. An authorized operator configures sensitive `DATABASE_URL` for production and preview in Vercel `applyai-api`; redeploy.
2. Confirm `/health`, `/ready`, web `/api/readiness` return 200. Record timestamps, deployment IDs and SHA.
3. Audit DB roles, RLS and source registry; ensure no permissive RLS workaround.
4. In staging, configure one authorized public ATS feed; persist source identity, terms, refresh cadence and provenance.
5. Trigger initial ingestion through existing registry/outbox/worker path; verify a source run, queued task, persisted job, canonical apply URL and candidate search result.
6. Run `pnpm job-supply:initial-acceptance` in a controlled environment with explicit evidence; do not weaken the strict `pnpm job-supply:acceptance` gate.
7. Exercise incremental refresh, duplicate suppression, closure, retries, lease expiry, dead letters, idempotency and failure recovery.
8. Establish scheduler/worker execution outside request lifecycle, metrics, alerts, runbook and freshness SLO.
9. Measure throughput, source coverage, provider limits and cost before proposing 2 million refreshed jobs/day.

## Release evidence table
| Gate | Status | Evidence |
|---|---|---|
| Runtime database connectivity | BLOCKED | API and web readiness HTTP 503 |
| Authorized source configured | UNVERIFIED | None |
| Scheduled worker operational | UNVERIFIED | None |
| Real source -> Job Radar | UNVERIFIED | None |
| Initial job supply acceptance | NOT RUN IN THIS AUDIT | package script exists |
| 2M refreshes/day | NOT DEMONSTRATED | No production throughput measurement |
| Stripe entitlements | UNVERIFIED | Must test before monetization |

## Release rule
No production-ready or monetization claim until every critical gate has exact-SHA CI, staging and live evidence, with independent GitHub review and explicit deployment authorization. Track progress in issues #90 and #91.
