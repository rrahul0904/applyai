# Data Model

## Identity and ownership

- `users`: internal UUID, unique `clerk_user_id`, profile fields, account and
  onboarding state.
- All candidate-owned rows reference `users.id`.
- Client-supplied user IDs are not accepted by candidate APIs.

## Candidate knowledge

- `candidate_profiles`: summary-level career representation.
- `candidate_experiences`, `candidate_education`, `candidate_skills`.
- `candidate_preferences`, `candidate_target_roles`.
- Extracted fields carry provenance values such as `USER_VERIFIED`,
  `DOCUMENT_EXTRACTED`, and `AI_INFERRED`.

## Resumes

- `resumes`: logical candidate-owned document.
- `resume_versions`: immutable upload metadata and storage reference.
- `resume_extractions`: parser version, extracted text/structure, status, error.
- Binary content lives in object storage, never PostgreSQL.

## Canonical job graph

```text
Company
  ├─ CompanyAlias
  ├─ CompanySource
  └─ Job
       ├─ JobLocation
       ├─ JobCompensation
       ├─ JobRequirement
       ├─ JobSkill
       ├─ JobVersion
       ├─ JobStatusHistory
       └─ JobSourceLink ── JobSource ── RawJobPosting
```

Source records are preserved. Deduplication links them to one canonical job
without destructive loss.

## Candidate workflow

- `saved_jobs`: candidate/job composite key.
- `applications`: current status with unique candidate/job constraint.
- `application_events`: immutable status history and actor.
- `application_documents`, `application_answers`, `application_notes`.
- `interviews`, `notifications`.

## Employer foundation

`employer_organizations` and `organization_members` establish future
organization-scoped authorization. Employer workflows are not implemented.

## Migration policy

Production never calls `create_all`. Every schema change requires a reviewed
Alembic revision, forward test, safe rollback test where possible, and drift
check.
