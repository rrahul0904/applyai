# Implementation Plan

## Milestone 0 — Architecture correction

- Official Next.js and FastAPI structure.
- PostgreSQL canonical model.
- Alembic migration discipline.
- Clerk identity and ownership boundary.
- Storage, queue, search, and connector interfaces.
- Foundation documentation and tests.

Exit: builds/tests/migration cycle pass; live Clerk configuration remains a
declared environment blocker rather than simulated authentication.

## Milestone 1 — Authenticated onboarding vertical slice

- Configure Clerk email and Google authentication.
- API client token forwarding.
- Internal user synchronization.
- Resume-less and resume upload onboarding.
- Resume worker processing and provenance review.
- Onboarding persistence and completion.

## Milestone 2 — Canonical jobs and candidate workflow

- Seed connector through the ingestion pipeline.
- URL-based PostgreSQL search/filter UI.
- Job detail, save/unsave, application creation, status events and history.
- End-to-end return-session persistence test.

## Milestone 3 — Real source proof

- One supported public connector.
- Raw capture, normalization, canonicalization, deduplication, freshness.
- Admin ingestion health visibility.

## Deferred

Explainable matching, AI tools, native mobile, employer product, and scale
infrastructure follow only after the first production vertical slice is
verified.
