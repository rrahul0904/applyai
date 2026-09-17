---
applyai_fit: PREPARE
fit_scope: FULL
destination: prepare
---

# Hirecast capability map

## ApplyAI Fit

`PREPARE / FULL`. Round-aware interview preparation, adaptive practice, readiness, STAR stories, private notes and evidence-backed company/interviewer research belong directly in ApplyAI's Prepare workspace.

## Why this qualifies

ApplyAI already owns the candidate evidence, job context, skill-gap analysis, application materials and interview engine. Hirecast-style mechanics improve continuity across interview rounds without creating a second candidate profile or a separate application system.

## Candidate journey stages

Learn skill gaps → prepare for interviews → practice/mock → measure readiness → manage career intelligence.

## Absorb into ApplyAI

- persisted job-specific interview preparation;
- recruiter, hiring-manager, technical/case and executive/culture round model;
- targeted practice questions with evidence-locked answer guidance;
- round quizzes and flashcards;
- one-page cheat sheet, private notes and retrospectives;
- retrospective carry-forward into later rounds;
- adaptive practice scoring, feedback, follow-ups and readiness;
- browser speech playback and speech-to-text fallback;
- persistent STAR story bank;
- reviewed research-source capture for company/interviewer evidence;
- optional private podcast/RSS preparation artifacts where they support candidate preparation.

## Keep separate

- any copied proprietary prompts, private content or hidden APIs;
- unsupported candidate claims generated from research;
- browser-direct access to ApplyAI business tables;
- a separate identity/profile system outside ApplyAI.

## Implementation destination

ApplyAI Prepare and interview workspace using the existing Career Memory, job context, evidence rules, FastAPI authorization and Supabase/RLS defense-in-depth.

## Implementation status

`IMPLEMENTED ON BRANCH; CONSOLIDATION REQUIRED`. PR #39 is green at its current head and has a working Vercel preview, but it is still draft and diverged from current `main`. Core Prepare functionality from the earlier integration wave is already merged; the additional round lifecycle, STAR/research and private feed features still require a current-main reconciliation and re-certification before production release.
