# ApplyAI Lean Production Architecture

Updated: 2026-08-31

## Launch profile

ApplyAI's initial production target is deliberately smaller than the existing AWS scale profile:

```text
Candidate
  -> Vercel / Next.js 16
  -> Clerk session/JWT
  -> Railway / FastAPI
       -> Railway PostgreSQL
       -> Cloudflare R2 (private S3-compatible storage)
       -> transactional TaskOutbox
            -> postgres_tasks
            -> Railway worker
```

The launch version does **not** require AWS.

## Responsibilities

| Concern | Lean production | Scale profile |
| --- | --- | --- |
| Candidate web | Vercel | Vercel |
| Identity | Clerk | Clerk |
| API | Railway FastAPI | ECS/Fargate FastAPI |
| PostgreSQL | Railway Postgres | Aurora PostgreSQL |
| Resume objects | Cloudflare R2 | private S3 |
| Durable queue | PostgreSQL | SQS |
| Outbox | PostgreSQL | PostgreSQL |
| Resume/source/AI worker | Railway | ECS/Fargate |
| Browser-heavy worker | isolated Railway service when enabled | ECS/Fargate |
| Infra definition | Railway project/service configuration | Terraform + bootstrap CloudFormation |

## Deployment profiles

`DEPLOYMENT_PROFILE=lean` is the launch profile.

Lean production requires:

```text
AUTH_PROVIDER=clerk
TASK_QUEUE_PROVIDER=postgres
OBJECT_STORAGE_PROVIDER=s3
DATABASE_URL=<managed PostgreSQL URL>
WEB_ORIGIN=https://...
CLERK_ISSUER=https://...
CLERK_JWKS_URL=https://...
```

`DEPLOYMENT_PROFILE=aws` keeps the established SQS/Aurora/S3 path.

Business logic must not branch on infrastructure provider. Provider differences remain inside database, queue and object-storage boundaries.

## Database

The API consumes one canonical `DATABASE_URL`. Railway's standard `postgresql://...` value is normalized to SQLAlchemy's installed psycopg dialect (`postgresql+psycopg://...`).

Legacy split variables remain available for the existing AWS runtime:

```text
DATABASE_HOST
DATABASE_PORT
DATABASE_NAME
DATABASE_USER
DATABASE_PASSWORD
```

When `DATABASE_URL` is explicitly supplied, it wins.

## Durable Postgres queue

The transactional outbox remains the first durability boundary. For the lean profile an outbox publisher materializes each task into `postgres_tasks` using a unique idempotency key.

Worker semantics:

- `QUEUED`
- `RUNNING`
- `RETRY_WAIT`
- `COMPLETED`
- `DEAD`
- `CANCELLED`

Claims use `SELECT ... FOR UPDATE SKIP LOCKED`. Running work has a lease owner, lease expiry and heartbeat. Expired leases are reclaimable after worker failure. Failed work retries with bounded exponential backoff and moves to `DEAD` after the configured attempt limit.

This keeps multiple Railway workers safe without Redis, Kafka or SQS.

## Object storage

The existing S3-compatible provider handles both AWS S3 and Cloudflare R2.

AWS scale profile:

```text
S3_SERVER_SIDE_ENCRYPTION=AES256
```

Cloudflare R2 launch profile:

```text
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_REGION=auto
S3_SERVER_SIDE_ENCRYPTION=none
```

The R2 mode omits the AWS `x-amz-server-side-encryption: AES256` PutObject header, which R2's S3 compatibility surface does not accept. R2 credentials remain server-side only.

Buckets must stay private. Resume Share Intelligence always serves through ApplyAI's controlled public route and never exposes the raw private object URL.

## Long-running work

Vercel is not used for:

- source crawling/ingestion;
- resume parsing;
- durable AI jobs;
- browser application execution.

Those are long-running Railway workers in lean production.

## AWS preservation

The following remain supported and validated as an optional future scale/enterprise profile:

```text
infra/bootstrap/*
infra/staging/*
Aurora
ECS/Fargate
SQS
S3
EventBridge
CloudWatch
```

Removing AWS from launch requirements does not authorize deleting or weakening those resources or their validation workflows.
