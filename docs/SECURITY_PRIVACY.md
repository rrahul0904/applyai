# Security and Privacy

## Current controls

- Clerk token signature and claim verification.
- Internal UUID identity distinct from email.
- Server-derived ownership on every candidate route.
- UUID foreign keys and database constraints.
- Resume type, extension, empty-file, and size validation.
- Storage keys omitted from API responses.
- S3 implementation requests server-side encryption.
- Immutable application status events.
- CORS restricted to the configured web origin.
- Candidate discoverability defaults to false.

## Required production controls

- Private S3 bucket, block public access, KMS encryption, lifecycle policy.
- Short-lived signed uploads/downloads where appropriate.
- Secrets in managed secret storage.
- Aurora TLS, encryption, backups, point-in-time restore, and connection pooling.
- SQS dead-letter queues and idempotency monitoring.
- Rate limiting, audit events, structured redaction, and dependency scanning.
- Data export and deletion workflows.

## Data minimization

Sensitive data is collected only when necessary. Candidate data is never sold.
AI personalization, contact visibility, employer discoverability, and
notifications remain explicit preferences.

## Threat boundaries

Search and AI indexes are derived state and must not bypass authorization.
Employer tenant access will require membership lookup rather than trusting
frontend roles or token-provided organization IDs.
