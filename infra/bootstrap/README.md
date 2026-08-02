# ApplyAI AWS bootstrap

This is the only one-time bootstrap step that requires an existing AWS administrator or equivalent provisioning identity. It creates the resources that cannot safely be created by the normal Terraform deployment before Terraform itself has remote state and GitHub has an AWS trust path.

The template creates:

- a dedicated encrypted/versioned/private S3 Terraform state bucket;
- a GitHub Actions OIDC provider for `token.actions.githubusercontent.com`, or reuses an existing provider ARN;
- a staging deployment IAM role trusted only by the ApplyAI GitHub `staging` environment;
- the permissions required by the current staging Terraform and release workflow.

Use a dedicated non-production AWS account for staging.

## Deployment-role scope

The GitHub deployment role is not an AWS administrator role.

The policy scopes:

- Terraform state access to the one bootstrap bucket;
- ECR, SQS, EventBridge, CloudWatch Logs, S3 and IAM mutations to ApplyAI staging name/ARN prefixes;
- `iam:PassRole` to ApplyAI staging roles and only the ECS Tasks and EventBridge services;
- RDS-generated secret reads to the managed `rds!cluster-*` secret namespace;
- regional control-plane access to the bootstrap stack's AWS Region.

A limited set of read/list APIs must use `Resource: "*"` because those APIs do not support resource-level ARNs. These are isolated in `RegionalReadOnlyDiscovery` and include repository, log-group, event-rule and queue discovery.

EC2, Elastic Load Balancing, ECS, RDS and CloudWatch provisioning still require account-scoped control-plane operations within the selected Region because their create/describe and dependency APIs do not have one uniform resource ARN that can cover a not-yet-created Terraform graph. This is why a dedicated staging account is required. Do not reuse this role as a production deployment policy without a separate production IAM review, permission boundary and CloudTrail monitoring.

Route 53 permissions are intentionally absent. DNS remains a separately reviewed operator action.

## Validate the template

```bash
cfn-lint infra/bootstrap/applyai-staging-bootstrap.yaml
```

CloudFormation lint validates template structure; the first real preflight and Terraform plan remain required to prove that the role has neither missing nor excessive permissions for the actual account.

## Deploy the bootstrap stack

From an authenticated AWS CLI session:

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --template-file infra/bootstrap/applyai-staging-bootstrap.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

Optional explicit state bucket name:

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --template-file infra/bootstrap/applyai-staging-bootstrap.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides StateBucketName=YOUR-GLOBALLY-UNIQUE-BUCKET
```

Read the values needed by GitHub:

```bash
aws cloudformation describe-stacks \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --query 'Stacks[0].Outputs' \
  --output table
```

Create a GitHub environment named `staging`, then set these environment variables:

```text
AWS_DEPLOY_ROLE_ARN=<GitHubDeployRoleArn output>
TF_STATE_BUCKET=<TerraformStateBucketName output>
AWS_REGION=us-east-1
```

The deployment workflows use GitHub OIDC (`id-token: write`) and do not require `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`.

## Existing GitHub OIDC provider

An AWS account can have only one provider for a given OIDC URL. In a shared account, find the existing provider ARN:

```bash
aws iam list-open-id-connect-providers --output table
```

Then deploy the bootstrap without creating another provider:

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --template-file infra/bootstrap/applyai-staging-bootstrap.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    CreateGitHubOidcProvider=false \
    ExistingGitHubOidcProviderArn=arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

A dedicated ApplyAI staging account can keep the default `CreateGitHubOidcProvider=true` path.

## GitHub environment protection

Before enabling deployment, configure the GitHub `staging` environment with:

- deployment branches restricted to `main` after the staging-hardening PR is merged;
- required reviewer approval for infrastructure apply, release and rollback when practical;
- no long-lived AWS credentials;
- values listed in `docs/STAGING_ENVIRONMENT_CONFIGURATION.md`.

The OIDC trust is scoped to the `staging` environment subject rather than all workflow runs in the repository. The template accepts both the conventional GitHub OIDC subject form and the immutable owner/repository-ID form.
