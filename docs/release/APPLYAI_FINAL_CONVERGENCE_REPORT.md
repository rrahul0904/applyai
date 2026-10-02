# ApplyAI final convergence report

## Release identity

The tested code checkpoint is commit `95f2cd38ebfc4e97599103b33cd385eed684acc9` on branch `codex/applyai-release-mission`, PR [#80](https://github.com/rrahul0904/applyai/pull/80), based on `main` `9798aa613c45cdf9d54f3e2c6c47481ca31d1852`. This follows `b6b7f70`, whose hosted run found a typed-mock error; the test mock was corrected in `95f2cd3`. All 21 required contexts and the full hosted suite passed on `95f2cd3`. The local migration head is `d0v4z6s9w197`; no claim is made about the production database revision. Vercel Preview deployment `6811587621` completed for this SHA at [Preview](https://applyai-f9ni042ii-rrahul0904-5013s-projects.vercel.app), but its runtime readiness is false. The prior pushed checkpoint `e38256b4d4a10eec54668853f6a6af0a29dda5c1` also passed certification; its bounded catalogue seed was skipped.

PR #80 requires one independent approval. GitHub reports `REVIEW_REQUIRED` / `BLOCKED`; no self-approval, branch-protection bypass or merge was performed. PR #82 remains open as the RE-370 source lineage.

Structured evidence is recorded in `artifacts/release/current-state.json`, `artifacts/release/capability-ledger.json`, `artifacts/release/resume-tailoring.json`, and `artifacts/release/remote-eligibility.json`.

## Reverse-engineering convergence

Tracker access returned HTTP 401 `AUTH_REQUIRED`, so this report records repository/GitHub evidence and does not claim external tracker reconciliation.

| Donor | ApplyAI destination | Evidence and remaining boundary |
|---|---|---|
| RE-001 Pinloop / RE-012 Pinloop | Job Radar, watches and saved searches | One capability family. Repository persistence and worker contracts exist; hosted scheduled refresh/delivery and real source receipts remain unverified. |
| RE-002 Dreamwork | Candidate-scoped MCP | Repository implementation exists; real external client handshake/OAuth and production verification remain unverified. |
| RE-003 Websumes | Resume, profile and portfolio | Existing shared candidate code is present; donor-specific workflow and hosted acceptance remain incomplete. |
| RE-004 JAN | Recruiter Lens | Evidence-backed repository workflow exists; hosted authenticated candidate journey remains unverified. |
| RE-005 ResumeShareIQ | Resume Share Intelligence | Persisted link/event code exists; separate-session event, bot filtering, privacy and notification acceptance remain unverified. |
| RE-006 Skilize | Prepare and Career | Skill-gap and preparation repository capabilities exist; complete hosted journey and human acceptance remain unverified. |
| RE-007 Hirecast | Interview runtime | Transcript privacy/ownership contracts exist; live capture/provider acceptance remains absent. |
| RE-008 Hack2Hire | Prepare question bank and workspace | Repository implementation exists; full candidate practice journey and human UAT remain incomplete. |
| RE-009 ai-job-search | Job supply and application preparation | Shared workflow exists; current authorized live-provider inventory is not measured. |
| RE-010 Jobber | Applications CRM | Candidate-controlled application preparation/handoff exists; external employer submission is not claimed. |
| RE-011 Camouflet / Terum Skills | ApplyAI Fit and evaluation | Deterministic evaluation gates exist; real model baseline, latency and cost evidence remain absent. |
| RE-208 ChannelPulse OSS | Interview privacy/lifecycle | Phase-A consent, retention, ownership and deletion contracts are repository implemented; native capture/live STT are not verified. No donor code/assets/prompts were copied. |
| RE-216 European Tech Opportunities / Issue #74 | Job supply lifecycle and provenance | Conservative source/lifecycle contracts exist; no live source coverage receipt is recorded. |
| RE-225 RemoteITJobs.net | Remote eligibility and source evidence | Lever, Ashby and authorized-feed adapters preserve explicit scope, country/region, source/application URLs, provenance, update timestamps, salary evidence and normalized facets/employment/seniority. Recommendation remote eligibility is gated before fit scoring when geography is known. 45 adapter/feed/authority/Radar tests and 3 candidate-workspace tests pass locally. No live RemoteITJobs crawl or registration is claimed. |
| RE-347 Openbound / Issue #77 | Sponsorship evidence | Phase-A evidence receipt/entity/posting/cap-exempt/correction contracts exist. Authorized live DOL ingestion, candidate evidence/correction journey and production verification remain incomplete. |
| RE-355 TexhPulze / Issue #79 | Evidence-locked Resume Studio | Numeric claim changes to tested currency/sign/magnitude/scientific-notation values are rejected. Candidate-owned PDF export has extractable text, true page count and no truncation; overflow is flagged. 27 focused backend tests, 2 UI tests and visual one-/multi-page review passed. DOCX, complete entailment, one-page composition mode and hosted journey remain incomplete. Universal ATS compatibility is not claimed. |
| JobPrime / Issue #75 | Job Radar discovery and delivery | Persisted search profiles/scans, scoring snapshots and durable worker contracts exist; real provider coverage, scheduled hosted receipts and candidate delivery remain unverified. |
| RE-370 Workmark / Issue #81 | Candidate Portfolio → Proof of Work Lab | Exact earlier Preview SHA `e38256b` returned 200 on the public GitHub metadata route for a bounded scan of six repositories with no source-body reads. This is a public-metadata prototype; private-repository consent, persistence, hiring evaluation and production use are not claimed. |

## Candidate features and live jobs

The release branch integrates candidate workspace/search, bounded role/skill/career recommendation ranking, application preparation, Job Radar, Resume Studio, Recruiter Lens, Prepare/interview workflows, resume sharing, candidate MCP, sponsorship evidence contracts, source lifecycle/provenance and the public proof-of-work prototype. The newest source additions include extractable PDF export, strict HTTPS validation for durable auth-verification endpoints and remote-source metadata/eligibility fixes.

Live job inventory and freshness are **NOT MEASURED**. The real provider seed was skipped in prior certification; repository fixtures and scale benchmarks do not substitute for a live source receipt. No LinkedIn or Indeed private scraping is implemented or claimed. Application support ends at candidate-controlled preparation and valid employer handoff; no external portal submission receipt is evidenced.

## Authentication, security and operations

Durable Clerk issuer/JWKS and Supabase project/JWKS endpoints now require absolute HTTPS URLs. Local auth configuration tests pass. Latest production and Preview readiness responses reported `runtime_ready=false`; the provider field was empty, Supabase configuration was present but instance matching was false. Google OAuth, real sign-up/login/callback/refresh/logout and authenticated candidate isolation remain unverified in a browser.

Admin/operator code and bootstrap paths exist, but no authenticated production operator session, worker heartbeat, production migration revision, deployed API/worker SHA or live queue receipt is available. Security tests cover the repository contracts; production DAST and authenticated production isolation remain unverified.

## Hosted verification and remaining blockers

Exact-head GitHub checks completed successfully on `95f2cd38ebfc4e97599103b33cd385eed684acc9`: all 21 required contexts passed. API tests/migration, web tests/lint/typecheck/build, API/worker image builds, Candidate MVP Playwright, OpenAPI, dependency/security/RLS checks, and source/search/agent scale benchmarks passed. Fresh-clone certification passed in 9m24s and repository-controlled predeploy passed in 14m22s. The bounded catalogue seed was skipped (`REQUIRE_REAL_INVENTORY=0`), so live job inventory is not measured. Runs: [CI](https://github.com/rrahul0904/applyai/actions/runs/37024998236), [security](https://github.com/rrahul0904/applyai/actions/runs/37024998205), [fresh clone](https://github.com/rrahul0904/applyai/actions/runs/37024998163), [predeploy](https://github.com/rrahul0904/applyai/actions/runs/37024998198), [search scale](https://github.com/rrahul0904/applyai/actions/runs/37024998340), [source scheduler](https://github.com/rrahul0904/applyai/actions/runs/37024997631), and [agent runtime](https://github.com/rrahul0904/applyai/actions/runs/37024998138). The prior `b6b7f70` attempt exposed a typed Blob-mock error, corrected in `95f2cd3`.

Preview deployment `6811587621` serves exact SHA `95f2cd3`; `/` and `/proof-of-work` return HTTP 200. The public GitHub metadata route returned HTTP 200 for `octocat`, scanning six repositories and reading no source bodies. `/api/readiness` returns HTTP 200 but `runtime_ready=false`, `production_ready=false`, `api_reachable=false`, `database_reachable=false`, `storage_configured=false`, `background_worker_configured=false`, and `supabase_instance_match=false` (observed 2026-10-02 15:11 UTC). Production readiness last returned HTTP 503 at 14:51 UTC. Neither result verifies authenticated or backend functionality.

Remaining blockers are the independent PR approval; exact-head checks and preview readiness for `b6b7f70`; unhealthy production/preview runtime; unknown live jobs/provider freshness, worker receipts and production migration; inaccessible reverse-engineering tracker; real Google/provider auth, operator and candidate-isolation browser tests; Resume Share separate-session acceptance; and five human UAT sessions. No production release is certified.

## Public claims supported

ApplyAI can describe a bounded public-GitHub-metadata proof-of-work prototype, evidence-locked resume claim checks, extractable paginated PDF export, and repository-tested remote eligibility/source provenance behavior. It can say the prior `e38256b` checkpoint passed its exact-head GitHub certification.

Do not claim production readiness, live job inventory size/freshness, hosted Radar scheduling, verified Google sign-in, successful employer submission, full donor-product parity, universal ATS acceptance or completion of human UAT.
