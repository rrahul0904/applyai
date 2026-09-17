---
applyai_fit: CORE
fit_scope: FULL
destination: candidate-core
---

# ApplyAI project reverse-engineering inventory

## ApplyAI Fit

This file is the project-level consolidation index for the reverse-engineering work captured in the ApplyAI project. It separates capabilities already live in ApplyAI from branch-only work and intentionally excluded product domains.

## Why this qualifies

The project has accumulated multiple reverse-engineering threads. Without one canonical map, code can exist on side branches while the production site gives the impression that the capability is complete. This inventory makes implementation and release state explicit.

## Candidate journey stages

Discover jobs → understand fit → improve resume/profile → apply → track → learn skill gaps → prepare for interviews → practice/mock → measure readiness → manage career intelligence.

## Absorb into ApplyAI

| Source / initiative | ApplyAI destination | Current state |
| --- | --- | --- |
| ApplyAI one-click application agent concept | application workflow + approval/handoff | Implemented in `main`; third-party submission remains a candidate-approved external handoff and does not bypass login/CAPTCHA |
| Job-source/admin architecture work | job supply + Operations | Implemented in `main`; durable source ingestion, quality, refresh, canonical jobs and operator certification exist |
| Pinloop | candidate core + Career Intelligence + alerts + MCP | Qualifying mechanics already implemented by existing ApplyAI capabilities |
| Dreamwork | external-agent integration | Implemented in `main` through the modern MCP endpoint and candidate-scoped tools |
| Skilize-style preparation/application materials | Prepare + Resume Studio | Implemented in `main` through application kit, learning paths, interview prep and evidence-safe PDFs |
| Hirecast | Prepare | Core overlap is live; additional round lifecycle / STAR / private-feed features remain on PR #39 pending current-main consolidation |
| Hack2Hire | Prepare + community/referrals | End-to-end branch implementation exists on PR #41 but is not merged because the branch diverged from newer `main` |
| Terum / Claude Skills evaluation mechanics | platform infrastructure | Implemented in `main` via reverse-engineering registry, fit classification and baseline/candidate release-evaluation gates |

## Keep separate

- generic agent/skill marketplaces that are not specific to the candidate journey;
- competitor proprietary content, hidden APIs, private prompts or private question banks;
- bypasses for third-party authentication, CAPTCHA or anti-bot controls;
- arbitrary code execution inside the primary FastAPI process;
- unrelated reverse-engineered products that belong to other project families rather than ApplyAI.

## Implementation destination

Canonical production targets are `apps/web`, `services/api`, `mobile`, `apps/extension`, the durable job-supply/worker architecture, and the production Vercel + backend deployment path. Side branches are not considered shipped until reconciled into `main`, re-certified, deployed and verified.

## Implementation status

`PARTIALLY COMPLETE AS A PROJECT CONSOLIDATION`.

As of 2026-09-17, `main` includes the core ApplyAI product, production job supply, Operations/admin, Supabase authorization hardening, application materials, learning/interview preparation, Dreamwork MCP interoperability, and the reverse-engineering fit/evaluation framework. The production web deployment for main commit `4092b4f3f9b8cb2cbc70410a589aa670ba46317d` is READY and the canonical landing page responds successfully.

Two meaningful reverse-engineered implementation lines still sit outside `main`: PR #39 (Hirecast extensions) and PR #41 (Hack2Hire interview intelligence/community/referrals). Neither should be called production-complete until reconciled against current `main`, all migrations/tests pass again, and the resulting exact commit is deployed and exercised through authenticated browser/API flows.
