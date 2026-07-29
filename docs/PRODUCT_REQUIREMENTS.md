# Product Requirements

## Current milestone

The first production vertical slice is:

REGISTER → AUTHENTICATE → ONBOARD → UPLOAD RESUME → REVIEW PROFILE → SEARCH
JOBS → VIEW JOB → SAVE JOB → CREATE APPLICATION → UPDATE STATUS → VIEW HISTORY
→ RETURN WITH DATA INTACT

## Acceptance requirements

Each capability is complete only when it has:

- authenticated and authorized API behavior;
- PostgreSQL persistence through Alembic migrations;
- validation and recoverable errors;
- responsive, accessible UI;
- loading and empty states;
- automated tests;
- documented contracts;
- no fabricated production data or AI output.

## Candidate foundation

- Internal users use UUID identity and map uniquely to Clerk.
- A candidate can access only their own profile, preferences, resumes, saved
  jobs, applications, notes, and documents.
- Onboarding can proceed without a resume.
- Resume facts retain provenance: `USER_VERIFIED`, `DOCUMENT_EXTRACTED`, or
  `AI_INFERRED`.
- Resume binaries remain outside PostgreSQL.

## Job foundation

- The UI reads canonical jobs from the API, never hard-coded cards.
- A canonical job may have multiple source records.
- Search supports keyword and structured filters with URL-represented state.
- Job detail exposes source, freshness, compensation provenance, and status.
- Disappearing jobs become historical records rather than being deleted.

## Explicit non-goals for this milestone

No arbitrary match percentages, autonomous applying, advanced Career Agent,
employer AI, native mobile, OpenSearch cluster, public pricing, or public launch
marketing.
