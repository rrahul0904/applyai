# PulseAtlas portfolio observability

ApplyAI remains authoritative for candidate profiles, resumes, applications, jobs, employers, AI artifacts, queues, billing and storage. PulseAtlas receives only privacy-safe observability facts.

## Web

The optional browser integration sends page paths with query/hash removed plus anonymous/session identifiers. It does not send candidate profile fields, resume content, job application answers, interview responses or private storage URLs.

## API

The API integration derives a small event set from HTTP method/path/success status only. It never reads request/response bodies. Current events are API health, application creation, and application status-change counts.

## Rich operational metrics

Do not duplicate ApplyAI's database into PulseAtlas. PulseAtlas should use ApplyAI's existing protected operator endpoints as adapters, including:

- `/api/v1/internal/job-supply/summary`
- `/api/v1/internal/ai-quality/metrics`

Those endpoints remain server-authoritative and require the existing internal operator token.

All PulseAtlas delivery is optional and fail-open.

Web configuration: `NEXT_PUBLIC_PULSEATLAS_ENDPOINT`, `NEXT_PUBLIC_PULSEATLAS_WRITE_KEY`, `NEXT_PUBLIC_PULSEATLAS_ENVIRONMENT`.

API configuration: `PULSEATLAS_ENDPOINT`, `PULSEATLAS_WRITE_KEY`, `PULSEATLAS_ENVIRONMENT`.
