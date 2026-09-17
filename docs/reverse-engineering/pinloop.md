---
applyai_fit: CORE
fit_scope: PARTIAL
destination: candidate-core
---

# Pinloop capability map

## ApplyAI Fit

`CORE / PARTIAL`. Pinloop-style job search, profile context, agent handoff, routines, schedules, saved work and AI-assisted ranking strengthen the ApplyAI candidate journey, but a separate generic agent platform or private server implementation does not belong inside ApplyAI.

## Why this qualifies

The publicly observed product model overlaps directly with ApplyAI's job discovery, saved searches, candidate profile, Career Memory, AI ranking, alerts, durable tasks and agent interoperability. ApplyAI should absorb the candidate-facing mechanics while retaining its own evidence model, authorization boundary and application-approval controls.

## Candidate journey stages

Discover jobs → understand fit → track → learn skill gaps → prepare → manage career intelligence.

## Absorb into ApplyAI

- profile-aware job discovery and ranking;
- reusable candidate context through Career Memory;
- saved searches, alerts, watches and scheduled refreshes;
- explainable AI judging through Career Intelligence rather than opaque hiring-probability claims;
- tabbed/organized candidate workflows in the Career Command OS;
- external-agent interoperability through the existing MCP boundary;
- durable workflow execution through ApplyAI's transactional outbox and PostgreSQL worker;
- auth and billing through ApplyAI's existing Supabase/Auth and entitlement architecture.

## Keep separate

- a generic agent marketplace;
- Pinloop-specific private server behavior or proprietary ingestion implementation;
- any hidden/private APIs or copied ranking prompts;
- non-career routines that do not strengthen the ApplyAI candidate journey.

## Implementation destination

Existing candidate shell, jobs/search, Career Intelligence, Career Memory, alerts/saved searches, MCP integration, billing and durable-task services.

## Implementation status

`IMPLEMENTED BY EXISTING CAPABILITIES` for the qualifying Pinloop mechanics. The remaining historical gaps identified during research (private server implementation and generic ingestion internals) are intentionally not copied; ApplyAI uses its own job-source platform and worker architecture instead.
