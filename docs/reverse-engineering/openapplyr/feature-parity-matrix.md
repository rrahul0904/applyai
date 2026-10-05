# OpenApplyr → ApplyAI feature parity matrix

Tracking issue: #84

| Capability | OpenApplyr observed | ApplyAI current state | Decision |
|---|---|---|---|
| Public job ingestion | ATS + aggregator registry/poller model | Durable source registry, public-page importer, Greenhouse/Lever/Ashby/SmartRecruiters/Open Jobs | Keep ApplyAI architecture; add missing reviewed adapters only |
| Greenhouse | Supported | Supported | No donor work |
| Lever | Supported | Supported | No donor work |
| Ashby | Supported | Supported | No donor work |
| SmartRecruiters | Supported | Supported | No donor work |
| Workday | Supported/documented | Not part of current canonical adapter list | Gap candidate |
| Workable | Supported/documented | Not part of current canonical adapter list | Gap candidate |
| Recruitee | Supported/documented | Not part of current canonical adapter list | Gap candidate |
| Generic public job import | Supported | Supported via bounded structured public-page importer | Keep ApplyAI implementation |
| Explainable job fit | Present | Career Intelligence deterministic baseline + durable AI V2 | Keep ApplyAI; no duplicate scorer |
| Resume tailoring | Present | Resume Studio + durable AI tailoring | Extend existing pipeline |
| Deterministic resume fact validation | Strong FactLock behavior | Evidence-bound artifacts exist, but this exact deterministic line/number/entity contract is not the canonical product contract | **Priority gap** |
| Cover letter | Present | Application copilot/durable artifacts | Keep; add package gate integration |
| Application question preparation | Present | Application copilot | Extend with required-answer/send gates |
| Unified pre-send gates | Explicit package gates | Approval boundary exists, but donor-style consolidated persisted gate set is not the documented canonical contract | **Priority gap** |
| Candidate approval before send | Default behavior | Explicit canonical boundary | Preserve |
| Bounded autopilot | Optional with gates | Do not currently claim third-party browser auto-submit in production | Future, gated only |
| Browser application runner | Supported for reviewed flows | Current third-party behavior is external handoff; browser auto-submit is optional/not production-claimed | **Future gap; high-risk** |
| CAPTCHA bypass | Explicitly not supported | Explicitly prohibited | Preserve refusal/pause boundary |
| Daily/search caps | Present | General durable task controls exist; application-specific pacing/cooldowns need dedicated contract | Gap candidate |
| Same-company cooldown | Present | Not canonical/documented as application policy | Gap candidate |
| Active-hours pacing | Present | Not canonical/documented as application policy | Gap candidate |
| Duplicate application protection | Present conceptually | Canonical applications exist; must verify/strengthen uniqueness before execution work | Gap candidate |
| Reply tracking from mailbox | Present | Notifications/application status exist; mailbox-derived stage inference is not a canonical claim | Future opt-in gap |
| Recruiter/hiring-manager outreach | Present | Recruiter/referral contacts and follow-ups exist | Extend only if mailbox/send boundary is proven |
| Interview preparation | Present | Already implemented | No duplicate subsystem |
| Offer comparison | Present | Not currently emphasized in canonical README | Optional later donor slice |
| Multiple AI providers | Broad provider catalog | Provider-reviewed AI boundary exists | Evaluate expansion only where operationally useful |
| Local model support | Present | Cloud/backend architecture; local deterministic substitutes for development | Optional companion capability, not core rewrite |
| Per-task model cost ledger | Present | Provider/model/token/cost metadata already recorded when available | Keep ApplyAI; consider candidate budget UX |
| Daily/monthly AI budget | Present | Billing/entitlements exist; explicit AI task budget is not canonical | Gap candidate |
| Local-first storage | Core | ApplyAI is cloud-first PostgreSQL/R2 | Reject topology clone |
| Desktop Electron shell | Core | Web + mobile + browser extension | Reject duplicate shell; optional constrained local runner only |
| Sample/demo workspace | Present | Historical demo/beta routes redirect to canonical product | Optional onboarding pattern, not priority |

## Priority order

1. FactLock-equivalent deterministic factuality validator.
2. Persisted unified application-package gates.
3. Application-specific pacing, duplicate and company-cooldown policy.
4. Workday/Workable/Recruitee ingestion coverage review.
5. Constrained browser runner proof on one reviewed ATS flow.
6. Opt-in mailbox reply tracking and evidence-backed stage updates.
7. Candidate-facing model/task budget controls and optional local-model companion.

## Completion rule

A row moves from gap to implemented only when there is repository evidence at an exact commit SHA plus focused tests. Browser/mail/provider-dependent rows additionally require real-environment verification before any production claim.