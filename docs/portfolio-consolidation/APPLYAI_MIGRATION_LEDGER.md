# ApplyAI Consolidation Ledger

Canonical repository: `rrahul0904/applyai`

## Deep-inspection correction to the portfolio audit

The first-pass portfolio audit grouped several career repositories under ApplyAI. Source-level inspection shows that not all of them should be merged as code.

| Repository | Decision | Evidence / rationale |
|---|---|---|
| `applyai` | **KEEP & INVEST / canonical** | Source-complete candidate + employer career platform with job supply, Career Intelligence, resume/application/interview workflows, mobile, extension, billing and governed agent runtime. |
| `ai-job-search` | **ARCHIVE_REFERENCE** | Repository README identifies the upstream project as `MadsLorentzen/ai-job-search`. Do not vendor upstream workflows, templates or assets into ApplyAI. |
| `jobber` | **ARCHIVE_REFERENCE** | README identifies the Sentient Engineering open-source project and external research lineage. Do not vendor its autonomous-browser agent into ApplyAI. |
| `resumeshareiq` | **SAFE_TO_DELETE_LATER** | Current repository contains only `REVERSE_ENGINEERING.md`; there is no product implementation to migrate. Backup/export before deletion. |
| `leetcode-platform` / Rigor | **KEEP_TEMPORARILY + INTEGRATE** | Rigor is a substantial independent technical-interview system with a controlled question factory and isolated Python/SQL execution boundaries. It should not be destroyed merely to reduce repository count. |

## Rigor integration boundary

ApplyAI owns candidate identity, job/application context, evidence, consent and the candidate interview experience. Rigor may become a specialized technical-assessment provider.

`services/api/app/interview_engine.py` introduces a stable provider contract:

- ApplyAI's deterministic evidence-locked interview engine remains the safe default.
- Coding/SQL questions are explicitly marked as requiring an execution boundary; they are never executed in the ApplyAI API process.
- A Rigor provider configuration is fail-closed by default.
- Enabling Rigor requires a reviewed authenticated API contract and a deployed Rigor execution service.
- Rigor remains authoritative for hostile-code isolation and its controlled question/content lifecycle.

## Retirement gates

- `ai-job-search`: archive/reference once repository administration is available. No code migration required.
- `jobber`: archive/reference once repository administration is available. No code migration required.
- `resumeshareiq`: safe-to-delete-later after backup/export.
- `leetcode-platform`: **NOT delete-ready**. Keep until the Rigor API contract, question entitlement/rights model and production execution boundary are explicitly accepted.
