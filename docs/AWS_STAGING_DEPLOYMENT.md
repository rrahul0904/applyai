# ApplyAI real AWS staging deployment

This is the authoritative execution order for deploying the merged ApplyAI platform to a real non-production environment. It covers the Candidate MVP plus Greenhouse, Lever, Ashby, career-site discovery and job URL import.

Local tests, Terraform validation, a running ECS task, or a successful `/health` response are not sufficient to call staging complete. The final gate requires real candidate acceptance, live-provider idempotency, failure recovery, rollback, backup recovery, observability and cost evidence.

## Frozen architecture

```text
Vercel / Next.js / Clerk
        ↓ HTTPS
AWS ALB
        ↓
FastAPI API on ECS/Fargate
        ↓
Aurora PostgreSQL Serverless v2
S3 direct resume uploads
PostgreSQL transactional outbox
Resume SQS + DLQ → resume worker
Source SQS + DLQ → source worker
EventBridge → bounded source dispatcher
CloudWatch logs and alarms
```

Do not introduce Kubernetes, Kafka, Redis, OpenSearch, a microservice split, AI matching, embeddings, auto-apply, employer tooling, billing or mobile work during this milestone.

## Current external boundary

The repository contains deployment source and validation workflows. Real deployment remains blocked until these external systems exist:

- dedicated or clearly isolated AWS staging account;
- GitHub `staging` environment and OIDC deployment role;
- Terraform state bucket;
- API hostname and issued ACM certificate;
- Clerk staging application and Candidate A/B identities;
- Vercel staging project/domain;
- reviewed public Greenhouse, Lever and Ashby source identifiers.

Never invent these values or commit credentials.

## Execution order

```text
1. CloudFormation bootstrap
2. GitHub staging environment
3. Clerk and Vercel staging
4. Staging preflight
5. Terraform plan and human review
6. Dormant Terraform apply
7. DNS/TLS
8. V2 immutable release with source dispatch disabled
9. V2 infrastructure verification
10. Candidate A/B acceptance
11. Manual Greenhouse/Lever/Ashby runs
12. Idempotency, dedup and lifecycle proof
13. URL-import security proof
14. Outbox/SQS/DLQ/lease recovery drills
15. Enable bounded source dispatcher
16. Rollback and backup-recovery drills
17. Cost and quality reports
```

## 1. Bootstrap AWS trust and Terraform state

Use an authenticated AWS administrator or equivalent only for this one-time step:

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --template-file infra/bootstrap/applyai-staging-bootstrap.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

When the account already has the GitHub OIDC provider, use the existing-provider parameters documented in `infra/bootstrap/README.md`.

Read outputs:

```bash
aws cloudformation describe-stacks \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --query 'Stacks[0].Outputs' \
  --output table
```

Verify the state bucket:

```bash
aws s3api get-public-access-block --bucket <TF_STATE_BUCKET>
aws s3api get-bucket-versioning --bucket <TF_STATE_BUCKET>
aws s3api get-bucket-encryption --bucket <TF_STATE_BUCKET>
```

Verify the deployment role trust policy allows only the ApplyAI repository and GitHub `staging` environment subject.

## 2. Configure GitHub, Clerk and Vercel

Create the GitHub environment:

```text
staging
```

Use `docs/STAGING_ENVIRONMENT_CONFIGURATION.md` as the exact variable contract. Do not store long-lived AWS access keys.

Create a separate Clerk staging application. Configure a non-empty backend audience and two non-production candidate identities. Development authentication must be disabled.

Create a Vercel staging project with values from `apps/web/.env.staging.example`. The Vercel origin must exactly match `WEB_ORIGIN`.

## 3. Run the required preflight

GitHub workflow:

```text
ApplyAI Staging Preflight
```

It must prove:

- GitHub OIDC role assumption;
- state bucket privacy, encryption and versioning;
- ACM certificate is issued in `AWS_REGION`;
- `WEB_ORIGIN`, `API_BASE_URL`, Clerk issuer and JWKS use HTTPS;
- Clerk issuer discovery and JWKS signing keys are reachable;
- Clerk audience is configured;
- Greenhouse, Lever and Ashby values are bounded JSON arrays;
- at least one reviewed public ATS source is configured.

Do not proceed while preflight is red.

## 4. Plan and review the dormant foundation

GitHub workflow:

```text
ApplyAI Staging Infrastructure
mode = plan
```

The workflow uploads:

```text
tfplan.txt
tfplan-summary.json
```

Complete `docs/STAGING_TERRAFORM_PLAN_REVIEW.md` using the real artifact. The workflow refuses any initial plan containing destroy actions.

Expected dormant state:

```text
API desired count                 0
resume worker desired count       0
legacy outbox desired count       0
source worker desired count       0
source-aware outbox desired count 0
legacy ingestion schedule         disabled
source dispatcher                 disabled
```

Expected resources include VPC, ALB, private ECS subnets, isolated database subnets, ECR, Aurora, private resume S3, resume/source SQS and DLQs, ECS task definitions, EventBridge dispatcher, CloudWatch logs/alarms and runtime IAM roles.

Reject the plan if it introduces a public database, public ECS tasks, public S3/SQS, unencrypted data stores, database ingress from `0.0.0.0/0`, duplicate queues/workers, unexpected replacement, or resource deletion.

## 5. Apply the dormant foundation

After plan approval:

```text
ApplyAI Staging Infrastructure
mode = apply
```

Capture the workflow run ID, Terraform outputs and AWS account/region in the acceptance report.

## 6. Configure API DNS and TLS

Point the staging API hostname to the ALB using Route 53 Alias records or the actual DNS provider.

Verify DNS and TLS without disabling certificate checks:

```bash
dig api.staging.example.com
curl -I https://api.staging.example.com/health
```

A 503 is acceptable before runtime activation; DNS and TLS must resolve correctly.

## 7. Release an approved main commit

GitHub workflow:

```text
ApplyAI Staging Release V2
```

Inputs:

```text
release_sha=<full commit contained in main>
source_worker_count=1
enable_source_dispatch=false
```

The workflow refuses commits not contained in `main`, builds/reuses the full-SHA ECR image, records the digest, runs a private one-shot Alembic migration task, aborts before activation if migration fails, and then activates:

```text
API                 1
resume worker       1
source worker       1
source-aware outbox 1
legacy outbox       0
legacy ingestion    disabled
source dispatcher   disabled
```

Record the source SHA, image URI/digest, task definition, migration task ARN, timestamps and exit code.

## 8. Verify deployed infrastructure

GitHub workflow:

```text
ApplyAI Staging Verification V2
expect_source_dispatch_enabled=false
```

The workflow requires:

- `/health`, `/ready` and healthy ALB targets;
- all four long-lived services running at nonzero desired count;
- one consistent runtime image;
- ECS task ENIs in private application subnets without public IPs;
- encrypted resume/source queues and valid DLQ redrive;
- private, encrypted, versioned resume bucket;
- available, encrypted Aurora with backup retention and a private DB instance;
- expected EventBridge dispatcher state;
- required runtime log groups and source alarms.

This is infrastructure verification only.

## 9. Candidate acceptance

Using real Clerk and Vercel staging:

1. Candidate A signs in.
2. Browser requests an upload intent.
3. Browser uploads directly to private S3.
4. API verifies the object with S3 HEAD.
5. ResumeVersion and outbox event commit atomically.
6. Source-aware outbox publishes `RESUME_PARSE`.
7. Resume worker processes the message.
8. Candidate reviews and confirms the profile.
9. Candidate completes job search, save and application workflows.
10. Candidate B direct API requests cannot access Candidate A data.

Test Candidate B isolation for profile, resume versions, saved jobs, applications, notes and job-import records. Do not rely only on hidden UI links.

## 10. Manual live provider validation

Register a small reviewed source set. Do not enable EventBridge yet.

For Greenhouse, Lever and Ashby:

- execute a manual run;
- record run/source IDs and all fetched/valid/invalid/created/updated/unchanged/deduplicated counts;
- execute the identical source again;
- prove no duplicate canonical job, source link or content version is created;
- prove `last_seen_at` and run evidence advance;
- preserve source URL, apply URL, external ID, raw payload, timestamps and field provenance.

For a multi-source job, prove the official ATS source remains primary and a lower-authority copy cannot overwrite canonical fields.

## 11. Job URL import and crawler security

Test:

- existing canonical job URL;
- new valid JSON-LD job page;
- results/listing page;
- malformed URL and unsupported scheme;
- localhost, private, link-local and cloud metadata destinations;
- redirect to a private address;
- robots-disallowed target;
- oversized response.

SSRF targets must be rejected before fetch, and every redirect hop must be revalidated.

## 12. Failure-recovery drills

Execute only controlled, reversible staging failures:

- pause source-aware outbox and prove the DB event remains durable;
- restart and prove logical exactly-once processing;
- force source-worker failure and observe visibility retry;
- allow a message to reach the source DLQ;
- inspect, correct and redrive idempotently;
- expire a source lease and prove one worker reclaims it;
- use a bad provider configuration and prove degradation/backoff/recovery;
- prove failed/partial runs create no negative freshness evidence.

## 13. Lifecycle and link validation

Prove:

```text
ACTIVE → UNKNOWN → STALE
explicit/repeated evidence → CLOSED
valid reappearance → ACTIVE
```

One timeout or one transient 404 must not close a job. A multi-source job remains active while one trustworthy source is fresh.

Apply-link validation may record `VALID`, `REDIRECTED`, `NOT_FOUND`, `FORBIDDEN`, `ERROR` or `UNKNOWN`, but must never submit an application.

## 14. Enable the bounded dispatcher

Only after manual provider and failure-recovery acceptance passes, rerun release/configuration with:

```text
enable_source_dispatch=true
```

Then run:

```text
ApplyAI Staging Verification V2
expect_source_dispatch_enabled=true
```

Start with one source worker and conservative limits. Observe queue depth/age, DLQ, worker CPU/memory, Aurora connections/capacity, source failure rate, invalid rate and dedup rate before increasing concurrency.

## 15. Rollback and recovery

Use the V2 rollback workflow with a prior full-SHA ECR tag. Verify all four runtime roles stabilize on the intended image, health/readiness pass, queues retain pending work and no Alembic downgrade occurs.

Demonstrate or validate:

- Aurora snapshot/PITR into a separate recovery target;
- S3 prior-version restoration using a test object;
- Terraform state prior-version retrieval;
- redeployment from an immutable ECR image.

## 16. Cost and quality evidence

Complete:

```text
docs/REAL_AWS_STAGING_ACCEPTANCE_REPORT.md
docs/AWS_STAGING_COST_REPORT.md
docs/LIVE_JOB_SOURCE_QUALITY_REPORT.md
```

Every cost figure must be labelled `MEASURED`, `CALCULATED FROM MEASURED INPUTS`, `PROJECTED` or `NOT MEASURED`.

Do not claim production economics, one million verified jobs, or provider coverage that was not executed.

## Completion rule

Real staging is complete only when AWS/Vercel/Clerk are deployed, Candidate A/B acceptance passes, all three providers pass idempotent live ingestion, URL import and multi-source dedup pass, retry/DLQ/lease recovery is demonstrated, rollback/backup recovery pass, CloudWatch is verified and cost/quality reports contain real measurements.

Until then:

```text
Real AWS staging = PARTIAL or BLOCKED
AI matching = NOT STARTED
AI matching remains blocked.
```
