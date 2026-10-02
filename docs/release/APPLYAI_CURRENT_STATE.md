# ApplyAI current state

Latest hosted observations: 2026-10-02 15:11–15:13 UTC (11:11–11:13 EDT). Latest local and GitHub inspection: 2026-10-02 15:26 UTC (11:26 EDT). Earlier checkpoints below are historical and must not be read as current runtime state.

## Latest evidence-backed state

| Item | Observed state | Evidence and boundary |
|---|---|---|
| Canonical repository and `main` | `rrahul0904/applyai`; `9798aa613c45cdf9d54f3e2c6c47481ca31d1852` | GitHub branch/API and local `origin/main` |
| Release candidate | PR #80, `codex/applyai-release-mission` → `main`; pushed head `95f2cd38ebfc4e97599103b33cd385eed684acc9` | [PR #80](https://github.com/rrahul0904/applyai/pull/80); exact-head suite passed; independent approval remains required |
| Other open donor PRs | #82 RE-370 `f7321e8`; #78 RE-347 `bb402e7` → #76; #76 JobPrime `4c8a0fc`; #73 ChannelPulse `a0d5802` | GitHub PR API. #82 is source lineage for code copied into the local #80 release worktree; no source PR was closed or merged |
| PR #80 checks and review | Exact head `95f2cd3` passed all 21 required contexts and the full hosted check set; the bounded catalogue seed was skipped. The first follow-on commit `b6b7f70` exposed a typed test mock error, fixed in `95f2cd3`. Independent approval has not been received. | [CI](https://github.com/rrahul0904/applyai/actions/runs/37024998236), [predeploy](https://github.com/rrahul0904/applyai/actions/runs/37024998198), [fresh clone](https://github.com/rrahul0904/applyai/actions/runs/37024998163), plus exact-head security/scale workflows. |
| Follow-on implementation | PDF export, durable auth HTTPS enforcement, ATS/authorized-feed evidence propagation, and pre-scoring remote eligibility updates are committed at `b6b7f70`; the test typing correction is `95f2cd3`. 88 focused API tests and 2 PDF UI tests pass locally; hosted API/web tests, typecheck, lint, builds, Playwright, security, scale, fresh-clone and predeploy checks pass on `95f2cd3`. | Exact-head [API/Web CI](https://github.com/rrahul0904/applyai/actions/runs/37024998236); [Candidate MVP Playwright](https://github.com/rrahul0904/applyai/actions/runs/37024998236); fresh-clone and predeploy links above. |
| Main branch protection | Enabled; strict up-to-date checks; 21 required contexts; one approval; stale reviews dismissed; last-push approval required; admin enforcement enabled; force push/deletion disabled | GitHub branch-protection API. No bypass or self-approval used. |
| Production web | `https://applyai-gold.vercel.app`; GitHub deployment `6593569358`; SHA `9798aa613c45cdf9d54f3e2c6c47481ca31d1852` | At 2026-10-02 14:51:58 UTC `/api/readiness` returned HTTP 503 and `runtime_ready=false`, `production_ready=false`, `api_reachable=false`, `database_reachable=false`, `storage_configured=false`, `background_worker_configured=false`, and `supabase_instance_match=false`. This does not identify which downstream service caused the backend readiness failure. |
| PR #80 preview | GitHub deployment `6811587621`; SHA `95f2cd38ebfc4e97599103b33cd385eed684acc9`; [Preview](https://applyai-f9ni042ii-rrahul0904-5013s-projects.vercel.app) | At 2026-10-02 15:11 UTC `/` and `/proof-of-work` returned 200; `/api/readiness` returned HTTP 200 with `runtime_ready=false`, `production_ready=false`, `api_reachable=false`, `database_reachable=false`, `storage_configured=false`, `background_worker_configured=false`, and `supabase_instance_match=false`. These values describe this Preview environment; they do not establish production service state. |
| Public route/auth probes | On Preview SHA `95f2cd3`, `/` and `/proof-of-work` returned 200 and `/api/proof-of-work/github?username=octocat&role=fullstack` returned 200 after scanning 6 of 6 bounded public repositories without source-body reads. Landing/sign-in/sign-up returned 200; unsigned candidate access redirected; identity API returned 401. Production `/job-radar` returned 404; preview redirected `/job-radar` to sign-in. | Read-only probes. The GitHub test identity produced zero recognized signal groups. No authenticated candidate/operator browser journey was performed. |
| API/worker deployment SHA, production migration revision, worker heartbeat/task receipts, live provider counts/freshness | Unknown | Not exposed by inspected deployment records or reachable readiness payload; no cloud/operator credentials available. |
| Repository migration head | `d0v4z6s9w197` | Local clean PostgreSQL upgrade, `alembic current`, and `alembic check` after the Job Radar snapshot migration. This is not proof of the production migration revision. |
| Reverse-engineering tracker | Not accessible | Fresh internal registry GET returned HTTP 401 `AUTH_REQUIRED`; no tracker rows were read or changed. |
| Human UAT | 0 of 5 recorded sessions | `artifacts/release/HUMAN_UAT_PLAN.md`; automated browser tests are not human UAT. |

Pushed source `95f2cd38ebfc4e97599103b33cd385eed684acc9` contains the follow-on PDF export, durable auth URL validation and RE-225 source evidence/eligibility changes. All 21 required contexts and the full hosted suite passed on this exact SHA; the catalogue seed was skipped. Fresh-clone certification passed in 9m24s and predeploy in 14m22s. The Preview deploys successfully and public landing/proof-of-work pages and the bounded GitHub metadata route return 200, but runtime readiness remains false. The branch remains below `PRODUCTION_VERIFIED` until a reviewed SHA has healthy hosted runtime, provider, operator, migration, isolation, accessibility, and human-UAT evidence.

## Historical checkpoint — 2026-10-01

The following source tables were written on October 1. Their exact branch, PR and deployment entries are retained as history; use the latest evidence-backed table above for present state.

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
