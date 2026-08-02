# ApplyAI AWS staging cost report

Do not enter fabricated numbers. Every value must be classified as one of:

```text
MEASURED
CALCULATED FROM MEASURED INPUTS
PROJECTED
NOT MEASURED
```

## Measurement identity

| Field | Value |
|---|---|
| AWS account classification | `BLOCKED — external input required` |
| AWS region | `BLOCKED — external input required` |
| Measurement start | `NOT MEASURED` |
| Measurement end | `NOT MEASURED` |
| Deployed Git SHA | `NOT MEASURED` |
| Terraform apply run | `NOT MEASURED` |
| Release run | `NOT MEASURED` |
| AWS Cost Explorer/Billing source | `NOT MEASURED` |

## Service costs

| Service/component | Quantity or usage | Cost | Classification | Evidence/source |
|---|---:|---:|---|---|
| Application Load Balancer | | | NOT MEASURED | |
| NAT gateway fixed hours | | | NOT MEASURED | |
| NAT data processing | | | NOT MEASURED | |
| Public IPv4 | | | NOT MEASURED | |
| ECS API Fargate vCPU/memory | | | NOT MEASURED | |
| ECS resume worker | | | NOT MEASURED | |
| ECS source worker | | | NOT MEASURED | |
| ECS source-aware outbox | | | NOT MEASURED | |
| ECS migration/dispatcher task runtime | | | NOT MEASURED | |
| Aurora Serverless v2 ACU hours | | | NOT MEASURED | |
| Aurora storage/I/O/backups | | | NOT MEASURED | |
| Resume S3 storage/requests | | | NOT MEASURED | |
| Resume SQS/DLQ requests | | | NOT MEASURED | |
| Source SQS/DLQ requests | | | NOT MEASURED | |
| CloudWatch logs | | | NOT MEASURED | |
| CloudWatch alarms/metrics | | | NOT MEASURED | |
| ECR storage/scanning/data transfer | | | NOT MEASURED | |
| Route 53/DNS | | | NOT MEASURED | |
| Other data transfer | | | NOT MEASURED | |

## Normalized operating metrics

| Metric | Value | Classification | Calculation |
|---|---:|---|---|
| Current daily cost | | NOT MEASURED | |
| Monthly equivalent | | NOT MEASURED | Daily measured cost × 30 only after a representative window. |
| Cost per source refresh | | NOT MEASURED | Source-platform cost / completed source runs. |
| Cost per 1,000 fetched postings | | NOT MEASURED | Source-platform cost / fetched count × 1,000. |
| Cost per 1,000 canonical active jobs | | NOT MEASURED | Allocated cost / verified canonical active jobs × 1,000. |
| Cost per 1,000 changed jobs | | NOT MEASURED | Allocated cost / created+updated canonical jobs × 1,000. |

## Required interpretation

Separate:

- fixed staging costs, especially NAT gateway, ALB and public IPv4;
- runtime-dependent ECS and Aurora costs;
- ingestion costs attributable to source refreshes;
- one-time validation costs such as restore drills;
- costs that would change materially under a production architecture.

A short staging window is not production economics. Any scale projection must list its measured inputs and assumptions.

## Current conclusion

```text
AWS cost measurement = NOT STARTED
```

Reason: real AWS staging infrastructure has not been deployed or observed.
