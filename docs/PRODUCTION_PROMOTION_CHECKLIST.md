# ApplyAI production promotion checklist

Production is intentionally not provisioned by the Milestone 2.6 staging stack. This checklist defines the gate for deriving the production environment after staging has been proven with real services.

## Required before creating production infrastructure

- all current-head CI gates green;
- real staging Clerk login and token verification complete;
- real browser -> S3 -> outbox -> SQS -> worker -> review -> confirm path complete;
- Candidate B isolation proven against Candidate A data;
- Greenhouse repeated-ingestion/change/freshness behavior proven in staging;
- DLQ failure/recovery procedure exercised;
- Aurora restore drill completed from a staging snapshot;
- S3 version recovery exercised for a test resume object;
- immutable ECR rollback exercised;
- CloudWatch alarms observed in OK/ALARM transitions;
- no sensitive resume body/token/password logging found;
- staging cost baseline recorded.

## Production-specific changes

Do not copy staging values blindly. Production should explicitly choose:

### AWS account and trust

- dedicated production AWS account;
- separate Terraform state bucket;
- separate GitHub `production` environment;
- production OIDC role trusted only by `environment:production`;
- required reviewer approval for apply/release/rollback;
- no long-lived AWS access keys.

### Database

- Aurora deletion protection enabled;
- final snapshot required on destroy/replacement;
- production backup/PITR retention selected explicitly;
- capacity floor/max based on staging measurements;
- RDS Proxy only when measured connection pressure/failover behavior justifies it;
- schema releases follow expand -> migrate -> contract so application image rollback remains possible.

### Networking

- multi-AZ production NAT/egress posture selected intentionally;
- ALB deletion protection enabled;
- production DNS/ACM isolated from staging;
- WAF considered from measured/public threat requirements rather than added by default.

### ECS

- API desired count >= 2 across AZs;
- worker/outbox capacity based on queue/outbox throughput measurements;
- deployment circuit-breaker/rollback behavior proven;
- autoscaling added only from measured CPU/request/queue targets;
- immutable image tags only.

### Storage and queue

- S3 lifecycle/retention policy reviewed against product/legal requirements;
- S3 Block Public Access remains enabled;
- SQS/DLQ redrive limits reviewed using staging failure tests;
- DLQ alert routing configured to an owned notification channel.

### Observability

- CloudWatch alarm actions routed to owned SNS/on-call destination;
- API 5xx/latency/unhealthy target alarms tuned from staging baseline;
- Aurora connection/capacity alarms tuned;
- queue depth/age/DLQ alarms tuned;
- log retention selected intentionally;
- dashboards/runbooks linked to deployment ownership.

### Web and identity

- production Vercel project/domain;
- production Clerk application;
- exact production `WEB_ORIGIN`;
- development auth disabled;
- production API domain and certificate.

## Production release gate

The production release workflow should preserve the staging release ordering:

```text
build immutable image
 -> push ECR
 -> run one-shot Alembic task
 -> abort on migration failure
 -> update ECS through Terraform
 -> wait service stability
 -> /health
 -> /ready
 -> candidate smoke test
```

Do not enable AI matching, embeddings, auto-apply, mobile, employer workflows, or billing merely as part of infrastructure promotion. Those remain separate product milestones.
