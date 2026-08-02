# ApplyAI real AWS staging acceptance report

This report must contain only executed evidence. Do not replace `BLOCKED` or `NOT STARTED` with completion language based on local tests, Terraform validation, screenshots, or intended architecture.

## Status summary

| Area | Status | Evidence |
|---|---|---|
| Candidate MVP source | COMPLETE | Merged before this staging milestone. |
| Job Source Platform V1 | COMPLETE | Merged before this staging milestone. |
| Career-site discovery and URL import | COMPLETE | Merged before this staging milestone. |
| Scale and quality source implementation | COMPLETE | Merged before this staging milestone. |
| Real AWS foundation | BLOCKED | AWS staging account and environment values have not been supplied in this branch. |
| API deployment | NOT STARTED | No real ECS release executed. |
| Vercel staging | BLOCKED | Vercel staging project and values are external inputs. |
| Clerk staging | BLOCKED | Clerk staging application and Candidate A/B identities are external inputs. |
| Resume workflow | NOT STARTED | Requires real Clerk, Vercel, S3, SQS, worker and Aurora. |
| Candidate isolation | NOT STARTED | Requires Candidate A/B staging identities. |
| Greenhouse ingestion | NOT STARTED | Requires reviewed live source and deployed runtime. |
| Lever ingestion | NOT STARTED | Requires reviewed live source and deployed runtime. |
| Ashby ingestion | NOT STARTED | Requires reviewed live source and deployed runtime. |
| URL import | NOT STARTED | Requires deployed API/source worker and a reviewed public URL. |
| Source retry and DLQ recovery | NOT STARTED | Requires real SQS/ECS runtime. |
| Rollback | NOT STARTED | Requires at least two immutable ECR images and deployed services. |
| Backup recovery | NOT STARTED | Requires real Aurora, S3 and Terraform state versions. |
| CloudWatch alarm delivery | NOT STARTED | Requires deployed alarms and optional SNS route. |
| AWS cost measurement | NOT STARTED | Requires actual staging usage. |
| AI matching | NOT STARTED | Remains blocked until all real-service staging gates pass. |

## Deployment identity

| Evidence | Value |
|---|---|
| Source branch | `agent/applyai-real-aws-staging` |
| Base main SHA | `7e87c8bea6c952b97e5bca2a4486bbdeaa3fb13a` |
| Approved deployment SHA | `NOT EXECUTED` |
| AWS account classification | `BLOCKED — external input required` |
| AWS region | `BLOCKED — external input required` |
| Terraform plan run | `NOT EXECUTED` |
| Terraform apply run | `NOT EXECUTED` |
| Release workflow run | `NOT EXECUTED` |
| Migration task ARN | `NOT EXECUTED` |
| ECR image URI/digest | `NOT EXECUTED` |
| Alembic head | `NOT VERIFIED IN AWS` |

## AWS foundation

Record the real deployed state:

| Resource | Identifier | Security/health evidence |
|---|---|---|
| VPC | `NOT EXECUTED` | |
| ALB | `NOT EXECUTED` | HTTPS target health required. |
| ECS cluster | `NOT EXECUTED` | |
| API service | `NOT EXECUTED` | Desired/running/pending counts and image digest. |
| Resume worker | `NOT EXECUTED` | Desired/running/pending counts and image digest. |
| Source worker | `NOT EXECUTED` | Desired/running/pending counts and image digest. |
| Source-aware outbox | `NOT EXECUTED` | Desired/running/pending counts and image digest. |
| Source dispatcher | `NOT EXECUTED` | Must remain disabled until manual providers pass. |
| Aurora | `NOT EXECUTED` | Private, encrypted, backup retention and availability. |
| Resume S3 | `NOT EXECUTED` | Public access block, encryption and versioning. |
| Resume queue/DLQ | `NOT EXECUTED` | Encryption, visibility and redrive. |
| Source queue/DLQ | `NOT EXECUTED` | Encryption, visibility and redrive. |

## Health and migration

| Check | Result | Evidence |
|---|---|---|
| `/health` | NOT STARTED | |
| `/ready` | NOT STARTED | |
| Migration task exit code | NOT STARTED | |
| `alembic current` | NOT STARTED | |
| `alembic check` | NOT STARTED | |
| ECS services stable | NOT STARTED | |

## Candidate acceptance

Record identifiers only; do not include tokens, passwords, resume contents or private notes.

| Check | Candidate A | Candidate B/isolation | Result |
|---|---|---|---|
| Clerk sign-in | NOT STARTED | NOT STARTED | |
| Direct S3 upload | NOT STARTED | N/A | |
| S3 HEAD verification | NOT STARTED | N/A | |
| Outbox → SQS → resume worker | NOT STARTED | N/A | |
| Resume review and confirmation | NOT STARTED | N/A | |
| Profile | NOT STARTED | Forbidden direct access test required | |
| Resume versions | NOT STARTED | Forbidden direct access test required | |
| Saved jobs | NOT STARTED | Forbidden direct access test required | |
| Applications and notes | NOT STARTED | Forbidden direct access test required | |
| Job-import records | NOT STARTED | Forbidden direct access test required | |

## Live provider evidence

Complete one row per reviewed source. Run each source twice to prove idempotency.

| Provider | Source ID | Public source | Run 1 | Run 2 | Fetched | Valid | Invalid/quarantined | Created | Updated | Unchanged | Deduplicated | Status |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Greenhouse | NOT STARTED | NOT STARTED | | | | | | | | | | NOT STARTED |
| Lever | NOT STARTED | NOT STARTED | | | | | | | | | | NOT STARTED |
| Ashby | NOT STARTED | NOT STARTED | | | | | | | | | | NOT STARTED |

Verify for every accepted posting:

- raw source payload retained without routine full-description logging;
- external source identity and URL retained;
- canonical/apply URL retained;
- company mapping and source trust recorded;
- first/last seen and fetched timestamps recorded;
- field-level provenance and primary source selected;
- unchanged second pass creates no duplicate canonical job, source link or content version.

## Deduplication and lifecycle

| Scenario | Status | Evidence |
|---|---|---|
| One canonical job with multiple source links | NOT STARTED | |
| Official ATS preferred over lower-authority source | NOT STARTED | |
| Lower-authority source cannot overwrite canonical fields | NOT STARTED | |
| Failed/partial source run creates no negative freshness evidence | NOT STARTED | |
| ACTIVE → UNKNOWN → STALE | NOT STARTED | |
| Explicit/repeated closure evidence → CLOSED | NOT STARTED | |
| Reappearance → ACTIVE | NOT STARTED | |
| Multi-source job remains active while one trusted source is fresh | NOT STARTED | |

## URL-import security

| Case | Expected | Result |
|---|---|---|
| Existing canonical job URL | Return/link existing canonical job | NOT STARTED |
| New valid JSON-LD job | Queue and extract | NOT STARTED |
| Listing page | Quarantine/reject | NOT STARTED |
| Invalid scheme | Reject before fetch | NOT STARTED |
| Localhost/private/link-local/metadata IP | Reject before fetch | NOT STARTED |
| Redirect to private IP | Reject redirect hop | NOT STARTED |
| Robots-disallowed target | Do not crawl | NOT STARTED |
| Oversized response | Abort within configured budget | NOT STARTED |

## Failure recovery

| Drill | Required evidence | Status |
|---|---|---|
| Pause source-aware outbox | Pending DB event survives; restart publishes once logically | NOT STARTED |
| Source worker controlled failure | Visibility retry and receive count increase | NOT STARTED |
| DLQ exhaustion | Message arrives after configured receives | NOT STARTED |
| DLQ recovery | Safe inspection, correction and idempotent redrive | NOT STARTED |
| Expired source lease | Reclaimable by one worker only | NOT STARTED |
| Bad provider configuration | Health degradation/backoff and later recovery | NOT STARTED |

## Rollback and recovery

| Check | Status | Evidence |
|---|---|---|
| Immutable rollback image exists | NOT STARTED | |
| API/resume/source/outbox rollback | NOT STARTED | |
| Health/readiness after rollback | NOT STARTED | |
| No database downgrade | NOT STARTED | |
| Queue messages survive rollback | NOT STARTED | |
| Aurora snapshot/PITR procedure | NOT STARTED | |
| S3 prior-version restore | NOT STARTED | |
| Terraform state prior-version retrieval | NOT STARTED | |

## Observability

| Check | Status | Evidence |
|---|---|---|
| API/worker/outbox/dispatcher/migration log streams | NOT STARTED | |
| API/ALB alarms | NOT STARTED | |
| Resume queue age/depth/DLQ alarms | NOT STARTED | |
| Source queue age/depth/DLQ/failure alarms | NOT STARTED | |
| Aurora CPU/capacity/connection alarms | NOT STARTED | |
| Safe alarm notification delivery | NOT STARTED | |
| Secret/PII log review | NOT STARTED | |

## Cost and quality

Do not fabricate values. Label each as `MEASURED`, `CALCULATED FROM MEASURED INPUTS`, `PROJECTED`, or `NOT MEASURED`.

| Metric | Value | Classification | Measurement window |
|---|---:|---|---|
| Daily staging cost | | NOT MEASURED | |
| Monthly equivalent | | NOT MEASURED | |
| Cost per source refresh | | NOT MEASURED | |
| Cost per 1,000 fetched postings | | NOT MEASURED | |
| Cost per 1,000 canonical jobs | | NOT MEASURED | |
| Cost per 1,000 changed jobs | | NOT MEASURED | |
| Valid posting rate | | NOT MEASURED | |
| Quarantine rate | | NOT MEASURED | |
| Deduplication rate | | NOT MEASURED | |
| Valid apply-link rate | | NOT MEASURED | |
| Salary/location/workplace coverage | | NOT MEASURED | |

## Final decision

Use one:

```text
COMPLETE
PARTIAL
BLOCKED
NOT STARTED
```

Current real AWS staging decision:

```text
BLOCKED
```

Current next-milestone decision:

```text
AI matching remains blocked.
```
