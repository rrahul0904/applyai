# ApplyAI AWS staging deployment

This runbook is the executable handoff for deploying the verified Candidate MVP backend to AWS while keeping the frozen architecture:

- Next.js web: Vercel
- identity: Clerk
- API/background runtimes: AWS ECS/Fargate
- PostgreSQL: Aurora PostgreSQL Serverless v2
- resume files: private S3
- task transport: SQS + DLQ
- logs/alarms: CloudWatch
- public job ingestion: scheduled Greenhouse Fargate task

No Redis, OpenSearch, Kafka, Kubernetes, RDS Proxy, microservice split, AI matching, or auto-apply is introduced here.

## Deployment phases

```text
0. One-time AWS bootstrap
   -> Terraform state bucket
   -> GitHub OIDC provider/reuse
   -> GitHub staging deployment role

1. External staging identities
   -> Clerk staging application
   -> Vercel staging project
   -> API hostname + ACM certificate

2. Preflight
   -> GitHub OIDC assumption
   -> state bucket privacy/encryption/versioning
   -> ACM ISSUED
   -> Clerk JWKS reachable
   -> environment value shape validation

3. Dormant AWS foundation
   -> VPC / ALB / ECS / ECR / Aurora / S3 / SQS / DLQ / IAM / CloudWatch
   -> API, worker, outbox desired count = 0
   -> ingestion schedule disabled

4. DNS
   -> API hostname alias/CNAME to ALB
   -> certificate coverage verified

5. Release
   -> build exact Git commit
   -> push immutable ECR tag
   -> run Alembic one-shot task
   -> abort if migration fails
   -> Terraform activates API/worker/outbox
   -> wait ECS stability
   -> /health + /ready

6. Infrastructure verification
   -> ECS/ALB/Aurora/S3/SQS/DLQ/CloudWatch

7. Real-service acceptance
   -> Clerk
   -> Vercel
   -> S3 direct upload
   -> PostgreSQL outbox
   -> SQS/DLQ
   -> worker
   -> Greenhouse
   -> Candidate A/B isolation
```

## 0. Required accounts and local tools

You need:

- AWS staging account (prefer a dedicated non-production account)
- GitHub admin access for `rrahul0904/applyai`
- Clerk staging application
- Vercel staging project
- DNS control for the staging hostname
- an ACM certificate in the same AWS Region as the ALB

For the one-time bootstrap machine/CloudShell:

```text
AWS CLI v2
CloudFormation access
```

Normal releases do not need a local AWS credential because GitHub Actions uses OIDC.

## 1. Bootstrap AWS trust and Terraform state

Run:

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --template-file infra/bootstrap/applyai-staging-bootstrap.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

When the AWS account already has `token.actions.githubusercontent.com` registered as an IAM OIDC provider, use the existing-provider path documented in `infra/bootstrap/README.md` instead of attempting to create a duplicate provider.

Read outputs:

```bash
aws cloudformation describe-stacks \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --query 'Stacks[0].Outputs' \
  --output table
```

Record:

```text
TerraformStateBucketName
GitHubDeployRoleArn
```

## 2. Create the GitHub `staging` environment

Repository:

```text
Settings -> Environments -> New environment -> staging
```

Recommended protection:

- restrict deployment to `main` once staging bring-up is complete;
- during initial bring-up, temporarily allow the milestone branch when required;
- optionally require a reviewer for plan/apply/release/rollback;
- never store static AWS access keys.

Set these **environment variables**:

```text
AWS_REGION=us-east-1
AWS_DEPLOY_ROLE_ARN=<GitHubDeployRoleArn>
TF_STATE_BUCKET=<TerraformStateBucketName>

WEB_ORIGIN=https://staging.example.com
API_BASE_URL=https://api.staging.example.com
API_CERTIFICATE_ARN=arn:aws:acm:us-east-1:ACCOUNT:certificate/...

CLERK_ISSUER=https://...
CLERK_JWKS_URL=https://.../.well-known/jwks.json
CLERK_AUDIENCE=

GREENHOUSE_BOARD_TOKENS=["board-token-one","board-token-two"]
```

The checked-in placeholder manifest is `infra/staging/github.environment.example`.

`GREENHOUSE_BOARD_TOKENS` is JSON, not a comma-separated string.

The current backend does not require the Clerk web secret key. Clerk secret/publishable keys belong in Vercel.

## 3. Configure Clerk staging

Create a separate Clerk application for staging.

Required backend values:

```text
CLERK_ISSUER
CLERK_JWKS_URL
CLERK_AUDIENCE (optional)
```

Required web values are documented in:

```text
apps/web/.env.staging.example
```

Create at least two staging candidates so authorization isolation can be proven with Candidate A and Candidate B.

Do not enable development auth in staging.

## 4. Configure Vercel staging

Connect the repository and use `apps/web` as the web application root/configured workspace according to the repository setup.

Configure:

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<Clerk staging publishable key>
CLERK_SECRET_KEY=<Clerk staging secret key>
APPLYAI_API_URL=https://api.staging.example.com
APP_ENV=staging
DEV_AUTH_ENABLED=false
DEV_AUTH_SECRET=
```

The Vercel staging origin must exactly match `WEB_ORIGIN` supplied to Terraform. The API rejects wildcard credentialed CORS.

## 5. Prepare API DNS and ACM

Use a dedicated hostname, for example:

```text
api.staging.example.com
```

Request/validate an ACM certificate in `AWS_REGION`. Store its ARN in the GitHub staging environment as `API_CERTIFICATE_ARN`.

DNS cannot be pointed to the ALB until the dormant foundation exists.

## 6. Run the staging preflight

Open GitHub Actions:

```text
ApplyAI Staging Preflight
```

This is the required external-prerequisite gate before Terraform plan/apply. It verifies:

- GitHub can assume the staging AWS deployment role through OIDC;
- the Terraform state bucket exists, is private, encrypted and versioned;
- the ACM certificate exists and is `ISSUED`;
- Clerk JWKS is reachable and contains signing keys;
- all URL variables use HTTPS;
- Greenhouse board tokens are valid JSON strings in an array.

Do not continue to foundation provisioning while preflight is red.

## 7. Provision the dormant AWS foundation

Open GitHub Actions:

```text
ApplyAI Staging Infrastructure
```

First run:

```text
mode = plan
```

Review the plan.

Then run:

```text
mode = apply
```

The workflow intentionally applies with:

```text
API desired count       0
worker desired count    0
outbox desired count    0
Greenhouse schedule     disabled
```

Expected resources include:

- VPC across two AZs
- internet-facing HTTPS ALB
- private ECS application subnets
- isolated DB subnets
- one staging NAT gateway
- ECR repository
- Aurora PostgreSQL Serverless v2
- RDS-managed database secret
- private/versioned/encrypted resume S3 bucket
- SQS queue + DLQ/redrive
- ECS cluster/task definitions
- EventBridge ingestion schedule (disabled)
- CloudWatch log groups/alarms

## 8. Point DNS at the ALB

Create the staging API DNS record using the ALB DNS name and zone information exposed by Terraform:

```bash
terraform -chdir=infra/staging output -raw api_alb_dns_name
terraform -chdir=infra/staging output -raw api_alb_zone_id
```

For Route 53, use an Alias A/AAAA record when possible.

Then verify TLS/DNS resolution:

```bash
curl -I https://api.staging.example.com/health
```

A 503 before application activation is acceptable; TLS and DNS must resolve correctly.

Do not release the Vercel client against the new API hostname until TLS/DNS are correct.

## 9. Run the first staging release

Open GitHub Actions:

```text
ApplyAI Staging Release
```

The release workflow:

1. assumes the AWS role through GitHub OIDC;
2. opens Terraform remote state;
3. resolves ECR/ECS networking from Terraform outputs;
4. builds `services/api` from the exact workflow commit;
5. tags the image with the full Git commit SHA;
6. reuses the image on an idempotent rerun if that immutable tag already exists;
7. registers a one-shot migration task using that exact image;
8. runs `alembic upgrade head` inside the private ECS network;
9. stops immediately if the migration task exits non-zero;
10. applies Terraform with API/worker/outbox desired count = 1;
11. optionally enables the Greenhouse schedule;
12. waits for all ECS services to stabilize;
13. verifies `/health` and `/ready` over the real HTTPS hostname.

Do not manually update ECS task definitions after this workflow becomes the deployment path. Terraform remains the control plane for service revisions.

## 10. Run infrastructure verification

Open:

```text
ApplyAI Staging Infrastructure Verification
```

It verifies the deployed AWS control-plane/data-plane facts that can be automated without candidate credentials:

- ECS API/worker/outbox are ACTIVE and running;
- ALB targets are healthy;
- Aurora is available, encrypted and private;
- resume S3 Block Public Access, encryption and versioning are enabled;
- SQS and DLQ exist with redrive configured;
- `/health` and `/ready` pass over HTTPS;
- CloudWatch log groups exist for API, worker, outbox, ingestion and migration.

This is infrastructure verification, not Candidate MVP acceptance.

## 11. Staging Candidate MVP acceptance gate

Infrastructure up is not acceptance. Prove the real Candidate MVP path.

### Authentication

- Candidate A signs up/signs in through real Clerk.
- API accepts Clerk JWT.
- refresh/relogin works.
- Candidate B cannot access Candidate A resources.

### Resume durability

Use a real PDF and DOCX within the configured limit.

Verify:

```text
browser
 -> upload intent
 -> presigned S3 PUT
 -> upload-complete HEAD verification
 -> ResumeVersion + task_outbox in one transaction
 -> outbox publisher
 -> SQS
 -> worker
 -> ResumeExtraction NEEDS_REVIEW
 -> candidate confirmation
 -> USER_VERIFIED profile
```

Confirm the browser sends file bytes directly to S3, not through the Vercel BFF.

### Failure injection

Safely test in staging only:

- temporarily scale the outbox service to zero;
- upload a resume;
- verify the resume + pending outbox row remain durable;
- restore the outbox service;
- verify the message reaches SQS and processes exactly once logically;
- test a controlled worker failure until the message reaches the DLQ;
- inspect only sanitized identifiers using `python -m app.ops.dlq` from an authorized task/session;
- restore/re-drive only after the cause is understood.

### Greenhouse lifecycle

For a small explicit public board set:

1. ingest once;
2. ingest the identical board again;
3. verify no duplicate canonical/source version is created while `last_seen_at` advances;
4. exercise a controlled changed posting fixture/source test and verify canonical search fields + `JobVersion` update;
5. exercise the configured missing-run thresholds and recovery to ACTIVE.

### Candidate workflow

Verify:

```text
login
onboarding
resume review/confirm
profile
preferences
job search/filter/pagination
job detail
save
create application
status APPLIED
note
logout/login
persistence
Candidate B isolation
```

## 12. Observability checks

Before calling staging verified, confirm:

- CloudWatch log streams exist for API, worker, outbox, ingestion, migration;
- ALB 5xx alarm exists;
- p95 API latency alarm exists;
- unhealthy target alarm exists;
- Aurora connection alarm exists;
- resume queue depth/age alarms exist;
- DLQ non-empty alarm exists;
- no resume body, Clerk token, password, or authorization header appears in routine logs.

Attach `alarm_sns_topic_arn` when notification routing is ready; alarms exist without requiring a notification channel.

## 13. Rollback

Use:

```text
ApplyAI Staging Rollback
```

Input an existing immutable ECR image tag, normally the full commit SHA from a prior release.

The workflow:

- verifies the image exists;
- reapplies Terraform with that image;
- keeps API/worker/outbox running;
- waits for ECS stability;
- verifies `/health` and `/ready`.

Database migrations are **roll-forward only**. The rollback workflow never runs Alembic downgrade. Only roll back to an application image compatible with the current schema. Schema-changing releases should use backward-compatible expand/migrate/contract sequencing.

## 14. Backups and recovery before production

Staging currently has Aurora automated backup retention configured. Before production promotion, prove:

- Aurora snapshot/restore into a separate recovery cluster;
- S3 version recovery for a test resume object;
- queue/DLQ operator procedure;
- redeployment from an immutable ECR image;
- Terraform state version recovery procedure.

Do not test destructive recovery against production first.

## 15. Production promotion gate

Do not create a production stack merely because staging infrastructure deploys.

Production Terraform should be derived only after the real staging gate passes and should then intentionally change:

- deletion protection and final snapshots;
- high availability/capacity minimums;
- NAT/AZ posture as required;
- alarm notification routing;
- GitHub `production` environment approval;
- production Clerk/Vercel domains;
- backup/PITR policy;
- optional RDS Proxy only if measured connection pressure justifies it.

See `docs/PRODUCTION_PROMOTION_CHECKLIST.md` for the full production gate.

AI matching, embeddings, mobile, employer tooling and billing stay outside this deployment milestone.
