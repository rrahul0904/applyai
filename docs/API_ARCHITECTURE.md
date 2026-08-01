# API Architecture

## Style

The FastAPI modular monolith exposes versioned JSON APIs under `/api/v1`.
Controllers validate and authorize requests; domain services own business rules.
OpenAPI is available at `/api/v1/openapi.json`.

## Current routes

- `GET /api/v1/me`
- `GET|PUT /api/v1/profile`
- `GET|POST /api/v1/resumes`
- `GET /api/v1/resumes/{resume_id}`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/saved`
- `GET /api/v1/jobs/{job_id}`
- `POST|DELETE /api/v1/jobs/{job_id}/save`
- `GET|POST /api/v1/applications`
- `GET /api/v1/applications/{application_id}`
- `PATCH /api/v1/applications/{application_id}/status`

## Boundaries

- Authentication: `verify_clerk_token`.
- Internal identity: `get_current_user`.
- Persistence: SQLAlchemy sessions.
- Search: `SearchProvider`.
- Objects: `ObjectStorageProvider`.
- Asynchronous work: `TaskQueue`.
- Ingestion: `JobSourceConnector`.

## Contract rules

- IDs are UUIDs.
- Candidate ownership comes from the token-derived internal user.
- Storage keys are never returned in public schemas.
- Status transitions append events in the same transaction.
- Expensive work is queued, not performed inside request handlers.
- Pydantic rejects invalid input before domain mutation.

## Planned

Generate the shared TypeScript API client from OpenAPI once the vertical-slice
contract stabilizes. Mobile will consume the same API and terminology.
