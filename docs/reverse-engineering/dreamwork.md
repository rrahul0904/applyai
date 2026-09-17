---
applyai_fit: INTEGRATION
fit_scope: PARTIAL
destination: external-integration
---

# Dreamwork clean-room reverse-engineering map

Date reviewed: 2026-09-16
Target product: https://www.dreamworkhq.com/
Target integration: ApplyAI

## ApplyAI Fit

**PARTIAL — APPLYAI INTEGRATION**

Dreamwork overlaps several ApplyAI candidate-facing workflows that already exist. The qualifying gap in this reverse-engineering slice is its bring-your-own-agent interoperability model, so the correct destination is an integration boundary rather than a duplicate candidate product.

## Why this qualifies

The public Dreamwork behavior maps directly to ApplyAI job discovery, candidate context, application pipeline, and human approval controls. Its MCP-style external-agent access is valuable because it lets specialized agents consume those existing ApplyAI capabilities without bypassing candidate identity or submission guardrails.

## Candidate journey stages

- `DISCOVER_JOBS` — external agents can search and browse active ApplyAI listings.
- `UNDERSTAND_FIT` — candidate context and match-oriented platform context can be exposed without cross-candidate access.
- `APPLY` — agents can prepare/stage an application but cannot submit around human approval.
- `TRACK` — staged applications enter the existing ApplyAI pipeline.

## Absorb into ApplyAI

- Bring-your-own-agent interoperability through a governed MCP boundary.
- Authenticated candidate context for external agents.
- Active job discovery/browse tools.
- Idempotent pipeline staging.
- A fail-closed approval boundary before employer submission.
- Protocol/header validation and candidate isolation.

## Keep separate

- A duplicate resume/profile model where ApplyAI already has one.
- A duplicate job ranking or application-material engine where ApplyAI already has those capabilities.
- Recruiter reply inbox behavior not certified by the public review.
- Guest resume-to-match demo behavior not certified by the public review.
- Dreamwork-specific pricing/usage-tier behavior.

## Implementation destination

`external-integration`

The implemented destination is ApplyAI's candidate MCP endpoint and existing guarded application workflow rather than a parallel Dreamwork-style product surface.

## Implementation status

**INTEGRATED — repository implementation**

The current ApplyAI repository includes the stateless candidate MCP contract, candidate-scoped tools, idempotent pipeline staging, approval-required application behavior, and isolation tests. Production OAuth/token onboarding, third-party MCP-client certification, hosted evidence, and browser evidence remain separate release gates.

## Clean-room boundary

This document records publicly observable product behavior and maps it to ApplyAI capabilities. It does not copy Dreamwork source code, private APIs, proprietary assets, prompts, or implementation details.

## Public behavior observed

Dreamwork publicly presents a resume-first job-search workflow that continuously ranks live jobs, creates role-specific application material, keeps applications in a pipeline, and requires candidate review/approval before application submission. Its public agent pages also advertise a bring-your-own-agent surface through MCP, including job discovery, pipeline staging, and application actions under the same approval guardrails.

Public references reviewed:

- https://www.dreamworkhq.com/
- https://www.dreamworkhq.com/agents
- https://www.dreamworkhq.com/ai-job-search-agent
- https://www.dreamworkhq.com/auto-apply-jobs
- https://www.dreamworkhq.com/ai-job-search

## Capability map

| Dreamwork-observable capability | ApplyAI status before this slice | This slice | Follow-up boundary |
| --- | --- | --- | --- |
| Resume-first candidate profile | Existing | Reused through candidate-scoped context | No duplicate profile model |
| Active job discovery | Existing | Exposed to external agents through `search_jobs` / `browse_listings` | Improve source breadth independently |
| Ranked/matched roles | Existing product surface | Not reimplemented | Expose richer match explanations to MCP later |
| Tailored application material | Existing agent/application material system | Not duplicated | Add explicit MCP pack-generation tool after existing service contract is reused |
| Application pipeline | Existing | External agents can idempotently stage a listing | Add richer pipeline retrieval/filtering if useful |
| Candidate approval before submit | Existing safety boundary | Preserved; MCP cannot submit or mark `APPLIED` | Wire an approval handle to the existing submission orchestrator rather than bypass it |
| Bring-your-own-agent / MCP | Gap | **Added** with modern stateless MCP transport | Add dedicated OAuth/API-token onboarding and broader client certification |
| Recruiter reply inbox | Not certified by this review | Not claimed | Separate milestone after repository/runtime review |
| Guest resume-to-match demo | Not certified by this review | Not claimed | Separate acquisition milestone |
| Usage-tier quotas / one-tap limits | Billing exists; exact parity not certified | Not claimed | Separate product/pricing milestone |

## Implemented MCP contract

Endpoint: `POST /api/v1/mcp`

Protocol revision: `2026-07-28`

The endpoint uses the authenticated ApplyAI candidate identity on every request and is stateless at the MCP transport layer. It supports:

- `server/discover`
- `tools/list`
- `tools/call`

Tools in the first slice:

- `get_platform_context` — candidate profile, resume readiness, pipeline summary, and guardrails.
- `search_jobs` — active listing search by text, location, and work mode.
- `browse_listings` — newest active listings with optional location/work-mode filters.
- `add_listing_to_pipeline` — idempotently creates a `PREPARING` application and audit event.
- `apply_to_job` — stages the application and returns `approval_required`; it does **not** submit externally and does **not** mark the application `APPLIED`.

## Safety and product invariants

1. Candidate scoping is derived from ApplyAI authentication, never from a caller-supplied candidate ID.
2. The MCP surface does not expose a cross-candidate selector.
3. Employer submission remains behind ApplyAI's existing candidate approval/submission workflow.
4. MCP never bypasses employer authentication, CAPTCHA, or private/unsupported application APIs.
5. `add_listing_to_pipeline` is idempotent for a candidate/job pair.
6. Modern MCP routing headers are validated against the JSON-RPC body.
7. MCP list/discovery results are marked `cacheScope: private` because the authorization context matters.

## Certification in this slice

`services/api/tests/test_mcp.py` covers:

- protocol discovery and deterministic tool listing;
- routing-header mismatch rejection;
- active-job search;
- idempotent pipeline staging;
- `apply_to_job` stopping at `approval_required` with no submission attempt;
- candidate isolation across authenticated identities.

Passing repository CI is required before this slice should be described as repository-certified. A deployed remote MCP endpoint, third-party MCP-client handshake, production OAuth/token onboarding, and browser/visual evidence are separate release gates and must not be inferred from repository tests.
