# ApplyAI staging infrastructure

This directory provisions the AWS half of the ApplyAI staging environment without
changing the frozen Candidate MVP architecture.

The stack contains:

- one VPC across two Availability Zones;
- public ALB subnets;
- private ECS/Fargate subnets with one staging NAT gateway;
- isolated Aurora PostgreSQL subnets;
- internet-facing HTTPS ALB for FastAPI;
- one immutable ECR repository shared by API, worker, outbox, migration, and ingestion tasks;
- Aurora PostgreSQL Serverless v2 with an RDS-managed master password in Secrets Manager;
- private versioned AES-256 S3 resume storage;
- SQS resume-processing queue plus DLQ and redrive policy;
- ECS services for FastAPI, resume worker, and outbox publisher;
- one-shot migration and Greenhouse ingestion task definitions;
- EventBridge schedule for Greenhouse ingestion, disabled until staging is activated;
- CloudWatch log groups and native API/Aurora/SQS alarms.

The web client remains on Vercel. Clerk remains the identity provider. Terraform
does not create a fake Vercel or Clerk environment.

## Required external inputs

Before a real apply, provide:

1. an AWS staging account or role with permission to create these resources;
2. a dedicated S3 bucket for Terraform remote state;
3. an ACM certificate for the staging API hostname;
4. DNS control for that API hostname;
5. a real Clerk staging application and its issuer/JWKS URL;
6. a Vercel staging project/origin;
7. explicit Greenhouse board tokens selected for staging validation.

Do not put Clerk secret keys, AWS access keys, database passwords, or Vercel tokens
in `terraform.tfvars`. Aurora owns the database password through Secrets Manager.
The FastAPI task receives the managed `username` and `password` fields as ECS
secrets and builds its PostgreSQL URL at runtime.

## 1. Configure remote state

Create a dedicated state bucket outside this stack, with Block Public Access,
versioning, and server-side encryption enabled. Then initialize:

```bash
cd infra/staging
terraform init \
  -backend-config="bucket=YOUR-TERRAFORM-STATE-BUCKET" \
  -backend-config="region=us-east-1"
```

The backend uses native S3 state locking through `use_lockfile = true`.

## 2. Configure inputs

```bash
cp terraform.tfvars.example terraform.tfvars
```

Replace the example Vercel origin, ACM certificate ARN, Clerk values, and initial
Greenhouse tokens. `terraform.tfvars` is intentionally gitignored.

Keep these at zero/disabled for the first infrastructure apply:

```hcl
api_desired_count          = 0
worker_desired_count       = 0
outbox_desired_count       = 0
ingestion_schedule_enabled = false
```

This provisions the infrastructure and task definitions without pretending an
image already exists in the newly-created ECR repository.

## 3. Validate and provision the dormant stack

```bash
terraform fmt -check -recursive
terraform validate
terraform plan
terraform apply
```

At this point the load balancer, private data plane, ECR, Aurora, S3, SQS/DLQ,
IAM, logs, alarms, and ECS task definitions exist, but application services are
not running.

## 4. Build and push the exact staging image

From the repository root:

```bash
AWS_REGION=us-east-1
ECR_REPOSITORY=$(terraform -chdir=infra/staging output -raw ecr_repository_url)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
    "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build -t applyai-api:staging services/api
docker tag applyai-api:staging "$ECR_REPOSITORY:staging"
docker push "$ECR_REPOSITORY:staging"
```

Use an immutable commit-derived tag for a shared staging environment rather than
reusing `staging`; set `image_tag` to that tag before the activation apply.

## 5. Run Alembic before starting services

The stack exposes a dedicated migration task definition. Run it in the private
application subnets:

```bash
CLUSTER=$(terraform -chdir=infra/staging output -raw ecs_cluster_name)
TASK=$(terraform -chdir=infra/staging output -raw migration_task_definition_arn)
SUBNETS=$(terraform -chdir=infra/staging output -json app_subnet_ids | jq -r 'join(",")')
SECURITY_GROUP=$(terraform -chdir=infra/staging output -raw ecs_security_group_id)

TASK_ARN=$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK" \
  --launch-type FARGATE \
  --network-configuration \
    "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}" \
  --query 'tasks[0].taskArn' \
  --output text)

aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN"
aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN" \
  --query 'tasks[0].containers[0].{exitCode:exitCode,reason:reason}'
```

Do not activate the API when the migration exit code is non-zero.

## 6. Activate staging services

After the image and migrations are verified, set:

```hcl
api_desired_count          = 1
worker_desired_count       = 1
outbox_desired_count       = 1
ingestion_schedule_enabled = true
```

Then:

```bash
terraform plan
terraform apply
```

Point the staging API DNS name at `api_alb_dns_name`. The ACM certificate supplied
to `api_certificate_arn` must cover that hostname.

Configure the Vercel staging project with its Clerk web credentials and the HTTPS
ApplyAI API URL. The FastAPI service uses Clerk JWT issuer/JWKS validation and does
not require the Clerk web secret key.

## 7. Required staging verification

Infrastructure creation alone is not a PASS. Verify in the real staging account:

```text
Clerk candidate A login
  -> Vercel Next.js
  -> FastAPI/ECS
  -> Aurora

resume upload intent
  -> browser presigned PUT
  -> private S3
  -> upload completion verification
  -> ResumeVersion + task_outbox transaction
  -> outbox publisher
  -> SQS
  -> resume worker
  -> extraction/review
  -> candidate confirmation
  -> profile persistence
```

Then deliberately pause or deny SQS publishing long enough to prove that the
resume and pending outbox event remain durable and process after recovery.

Run Greenhouse ingestion twice unchanged and prove there is one canonical job,
one source link, no duplicate version, and a refreshed `last_seen_at`. Then run a
controlled changed posting and prove canonical fields/search state update and a
new `JobVersion` appears.

Finally repeat the candidate journey with Candidate B and verify that Candidate B
cannot read Candidate A's resume, profile, saved jobs, application, or notes.

## Cost / scaling posture

This is a staging stack, not a production topology. It intentionally uses one NAT
gateway and one Aurora Serverless v2 instance to keep complexity and cost bounded.
RDS Proxy, Redis, OpenSearch, Kafka, Kubernetes, and service decomposition are not
part of this milestone. Add them only after measured load demonstrates a need.
