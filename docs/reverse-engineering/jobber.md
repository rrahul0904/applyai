---
applyai_fit: CORE
fit_scope: FULL
destination: candidate-core
---

# Jobber → ApplyAI Opportunity CRM

Date reviewed: 2026-09-19

Public target:
- https://github.com/jobber-app/jobber

## Clean-room boundary

ApplyAI reproduces the useful observable tracking model with original implementation. It does not copy Jobber source code, UI assets, Rails models, or project branding.

## ApplyAI Fit

**FULL — APPLYAI CORE**

Jobber's differentiator is a candidate-owned opportunity tracker that organizes applications by stage and keeps deadlines, interviews, offers, and notes visible together.

## Why this qualifies

ApplyAI already tracked recruiting status and notes, but a flat list made multi-opportunity management weaker than the public Jobber model. A stage board plus structured next actions, deadlines, interviews, sources, priorities, and offer details directly strengthens the `TRACK` stage of the candidate journey.

## Candidate journey stages

- `APPLY` — preserve opportunity context while preparing/submitting.
- `TRACK` — organize active pursuits by stage.
- `PREPARE_FOR_INTERVIEWS` — keep interview dates tied to the application.
- `CAREER_INTELLIGENCE` — compare pipeline movement and offers without losing provenance.

## Absorb into ApplyAI

- Stage-first opportunity board.
- At-a-glance counts by recruiting stage.
- Application deadlines.
- Interview date/time.
- Next-action date.
- Source/referral channel.
- Candidate priority.
- Offer minimum/maximum/currency and negotiation notes.
- Private application notes.
- Overdue-deadline signals.
- Durable event history and candidate ownership.

## Keep separate

- Jobber's Rails/SQLite implementation.
- Its original visual assets and branding.
- Legacy development architecture.
- Email-sending behavior that would bypass ApplyAI's existing candidate approval boundaries.

## Implementation destination

`candidate-core`

The implementation extends the existing ApplyAI `Application` and `ApplicationEvent` model. Structured tracker snapshots are auditable events rather than a second application system.

## Implementation status

**IMPLEMENTED — final donor consolidation**

ApplyAI now exposes a candidate-owned Opportunity CRM board grouped by stage, structured application tracker fields, offer tracking, overdue detection, and editable opportunity details while preserving the existing application agent, submission, status-history, note, and interview-preparation flows.
