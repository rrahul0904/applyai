# ApplyAI staging Terraform plan review

Complete this record for the exact Terraform plan artifact produced by `ApplyAI Staging Infrastructure` before applying the dormant foundation.

## Execution identity

| Field | Value |
|---|---|
| Git commit SHA | `NOT EXECUTED` |
| GitHub workflow run ID | `NOT EXECUTED` |
| AWS account classification | `BLOCKED — external input required` |
| AWS region | `BLOCKED — external input required` |
| Terraform state bucket | `BLOCKED — external input required` |
| Plan artifact | `NOT EXECUTED` |
| Reviewer | `NOT ASSIGNED` |
| Review date | `NOT EXECUTED` |

## Expected foundation

The approved plan should create or update only the reviewed staging architecture:

- VPC spanning two availability zones;
- public HTTPS ALB subnets;
- private ECS application subnets;
- isolated database subnets;
- ECS cluster and dormant API/resume/source/outbox services;
- exact-image migration and source-dispatch task definitions;
- ECR repository;
- Aurora PostgreSQL Serverless v2 and managed database secret;
- private, encrypted, versioned resume S3 bucket;
- resume SQS queue and DLQ;
- source SQS queue and DLQ;
- disabled legacy ingestion schedule;
- disabled source EventBridge dispatcher;
- CloudWatch logs and alarms;
- separate least-privilege runtime roles for API, resume worker, resume outbox, source worker, source-aware outbox and database-only tasks;
- a separate ECS execution role limited to image pull, logging and database-secret injection.

## Automated plan summary

The workflow uploads:

```text
infra/staging/tfplan.txt
infra/staging/tfplan-summary.json
```

Record the counts from `tfplan-summary.json`:

| Action | Count | Review |
|---|---:|---|
| Create | `NOT EXECUTED` | Pending |
| Update | `NOT EXECUTED` | Pending |
| Replace | `NOT EXECUTED` | Pending |
| Destroy | `NOT EXECUTED` | Must be zero for the initial dormant apply |

## Security review

Mark each item only after reading the real plan:

- [ ] Aurora has no public endpoint.
- [ ] ECS tasks run without public IP addresses.
- [ ] Database ingress is limited to the application security group.
- [ ] Resume S3 blocks all public access and uses encryption/versioning.
- [ ] Resume and source queues use encryption and DLQ redrive.
- [ ] No long-lived AWS access keys are created.
- [ ] GitHub OIDC deployment role remains scoped to the `staging` environment.
- [ ] No wildcard credentialed CORS origin is introduced.
- [ ] API role can access only required resume objects and has no queue-consumer permissions.
- [ ] Resume worker role can read resume objects and consume only the resume queue.
- [ ] Resume-only outbox can publish only to the resume queue.
- [ ] Source worker can consume only the source queue.
- [ ] Source-aware outbox can publish only to the resume and source queues.
- [ ] Migration, legacy ingestion and source-dispatch tasks use a database-only task role with no S3/SQS policy.
- [ ] ECS execution role is separate from runtime roles.
- [ ] Legacy Greenhouse schedule is disabled.
- [ ] Source dispatcher is disabled.
- [ ] API, resume worker, legacy outbox, source worker and source-aware outbox desired counts are all zero.
- [ ] No unreviewed resource deletion or replacement is present.

If this is not a fresh account and the plan removes the previous shared ECS task role, stop and review that role migration explicitly rather than bypassing the destroy gate.

## Cost-sensitive resources

Record the planned quantities and the reason each is required:

| Resource | Planned quantity/configuration | Review note |
|---|---|---|
| NAT gateway | `NOT EXECUTED` | Largest fixed networking cost; confirm staging design. |
| Public IPv4 | `NOT EXECUTED` | Confirm only ALB/NAT requirements. |
| ALB | `NOT EXECUTED` | Required for HTTPS API ingress. |
| Aurora ACU range | `NOT EXECUTED` | Confirm staging minimum/maximum. |
| ECS desired counts | `0` expected | Dormant foundation only. |
| CloudWatch log retention | `NOT EXECUTED` | Confirm staging retention. |
| Alarm SNS actions | `NOT EXECUTED` | Optional until notification channel exists. |

## Decision

Use one value:

```text
APPROVED
REJECTED
BLOCKED
```

Current decision:

```text
BLOCKED
```

Reason: no real AWS plan has been executed or reviewed yet.
