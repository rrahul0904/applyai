# ApplyAI current state

Checked 2026-10-01 19:11 EDT (2026-10-01 23:11 UTC). These values come from the checked-out Git refs, GitHub API/CLI, the deployed readiness endpoints, and the repository migration graph. Unknown values are called out explicitly.

## Source and release identity

| Item | Observed state | Evidence |
|---|---|---|
| Canonical repository | `rrahul0904/applyai` | Git remote `origin` |
| `main` | `9798aa613c45cdf9d54f3e2c6c47481ca31d1852` | `git rev-parse origin/main`; GitHub API |
| Current implementation branch | `codex/applyai-release-mission` at `7fe52aec141180e86a5bdb70e939a474d845aec6` | `git rev-parse HEAD`; PR #80 |
| Working tree at inspection | clean | `git status --short` |
| Remote branch refs | 81 refs visible locally after fetch | `git for-each-ref refs/remotes/origin`; refs may include stale branches |
| `main` protection | enabled; strict up-to-date checks; 1 approval; 21 required contexts | GitHub branch-protection API |

## Open relevant pull requests and issues

| Item | State and lineage | Evidence |
|---|---|---|
| PR #80 | Open draft, `codex/applyai-release-mission` (`7fe52ae`) → `main` (`9798aa6`) | GitHub PR API |
| PR #78 | Open draft, `feature/re347-immigration-evidence-phase-a` (`bb402e7`) → `reverse/applyai-jobprime-radar` (`4c8a0fc`) | GitHub PR API |
| PR #76 | Open draft, `reverse/applyai-jobprime-radar` (`4c8a0fc`) → `main` | GitHub PR API; PR #78 is stacked on this branch |
| PR #73 | Open draft, `reverse-engineering/channelpulse-oss-20260922` (`a0d5802`) → `main` | GitHub PR API |
| Issue #74 | Open; European Tech Opportunities donor → Radar lifecycle/provenance | GitHub issue API |
| Issue #75 | Open; JobPrime Job Radar implementation and scheduled match delivery | GitHub issue API |
| Issue #77 | Open; Openbound sponsorship evidence integration | GitHub issue API |
| Issue #79 | Open; TexhPulze resume-tailoring donor | GitHub issue API |

The GitHub API returned the above open donor/release PRs in the repository's PR listing. There are 81 local remote refs; a ref's existence alone does not establish that its work is active or merged.

## Hosted deployments

| Surface | Observed identity | Readiness |
|---|---|---|
| Production web alias | `https://applyai-gold.vercel.app`; latest GitHub Production deployment `6593569358`, SHA/ref `9798aa613c45cdf9d54f3e2c6c47481ca31d1852`, created `2026-09-22T14:51:49Z` | `/api/readiness` returned `runtime_ready=true`, `production_ready=false`; `operator_configured=false` |
| Current PR Preview | `https://applyai-dsj8f4a3j-rrahul0904-5013s-projects.vercel.app`; deployment `6794165257`, SHA/ref `7fe52aec141180e86a5bdb70e939a474d845aec6` | `/api/readiness` returned `runtime_ready=true`, `production_ready=false`; `operator_configured=false` |
| API deployment SHA | Not exposed by the reachable readiness response or inspected GitHub deployment record | Unknown; no SHA alignment claim |
| Worker deployment SHA/heartbeat | Not exposed by the inspected readiness response or GitHub deployment record | Unknown; no hosted worker-execution claim |

Both readiness responses report API/database/storage/background-worker configuration true, `auth_provider=supabase`, Supabase auth configured and instance match true, and dev auth disabled. Both report `operator_auth_location=database` but no configured operator. The web readiness payload also reports Clerk compatibility fields; Supabase is the active reported auth provider. The backend database host/provider beyond reachable database readiness is not independently exposed by this endpoint.

## Database and source runtime

| Item | Observed state | Evidence |
|---|---|---|
| Repository Alembic head | `c9u3y5r8v086` (`interview_transcript_privacy`) | `services/api/.venv/bin/alembic heads` |
| Deployed production migration revision | Unknown | Hosted readiness does not expose it; no authenticated operations session |
| Production job-source runtime | Provider code/configuration exists in repository; live source inventory, active source counts, freshness, and ingestion receipts were not exposed in the inspected readiness endpoint | Repository inspection and hosted readiness |
| Live real-job counts/freshness | Unknown | No authorized live inventory evidence observed |
| Tracker access | Not available in this environment: prior internal tracker endpoint returned HTTP 401; no connected tracker app/tool is exposed | Prior endpoint result and current tool inventory |

## Verification boundary

The last exact-head PR #80 certification recorded before this fresh state check is at `7fe52aec141180e86a5bdb70e939a474d845aec6`; its required GitHub checks passed, but its full-functional job explicitly ran with `REQUIRE_REAL_INVENTORY=0`. The candidate browser suite used test identities/data. These repository/Preview results do not establish production readiness, live provider operation, human UAT, production API/worker SHA alignment, or production migration state.

## Subsequent release checkpoint — 2026-10-02 02:33 UTC

| Item | Current evidence | Boundary |
|---|---|---|
| Release branch / PR #80 | `codex/applyai-release-mission` at `ca5714855beb80228b23d920b47e0c5b96d8342a`; PR remains open draft to `main` at `9798aa613c45cdf9d54f3e2c6c47481ca31d1852`; review is required | No merge or production promotion occurred |
| Vercel Preview | Deployment `6799859834`, exact SHA `ca5714855beb80228b23d920b47e0c5b96d8342a`, URL [Preview](https://applyai-gnq662g1u-rrahul0904-5013s-projects.vercel.app) | `/api/readiness` returned HTTP 200, `runtime_ready=true`, `production_ready=false`; API/database/storage/background/auth checks true, Supabase active and instance matched, development auth false, `operator_configured=false` |
| Exact-head backend/browser checks | GitHub Actions [ApplyAI CI](https://github.com/rrahul0904/applyai/actions/runs/36955782577): API tests **395 passed, 1 skipped**; migrations-from-zero/head validation passed; candidate Playwright **11 passed, 5 skipped**; web tests, typecheck, lint, production build, API and combined worker images passed | Evidence uses deterministic test identities/data, not real provider accounts |
| Hosted scale/security checks | Search benchmark passed at 10k/50k/250k jobs; source scheduler passed at 1k/10k/50k sources; agent runtime passed at 1k/10k/50k runs; security scans, RLS/schema, workflow lint, Terraform and queue/R2 compatibility passed | Synthetic benchmark scale is not live inventory volume or provider operation |
| Final exact-head workflows | Fresh-clone certification [run](https://github.com/rrahul0904/applyai/actions/runs/36955782616) passed in 8m51s; no-deploy predeploy certification [run](https://github.com/rrahul0904/applyai/actions/runs/36955782551) passed in 8m53s | Predeploy explicitly ran with `REQUIRE_REAL_INVENTORY=0`; bounded catalogue seed skipped |
| Production and live data | Production remains deployed at main SHA `9798aa613c45cdf9d54f3e2c6c47481ca31d1852`; a fresh `/api/readiness` request returned HTTP 503 while reporting `runtime_ready=true`, `production_ready=false`, and `operator_configured=false`; API/worker SHA and deployed migration revision remain unexposed; live-job counts/freshness remain unmeasured | No real-provider, production behavior, operator bootstrap, or human UAT claim |

All observed PR #80 contexts for `ca5714855beb80228b23d920b47e0c5b96d8342a` completed successfully, except the intentionally skipped bounded catalogue seed and credential-gated Playwright cases. PR #80 is still draft and review-required; no merge or production deployment followed.
