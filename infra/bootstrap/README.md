# ApplyAI AWS bootstrap

This is the only one-time bootstrap step that requires an existing AWS administrator or equivalent provisioning identity. It creates the resources that cannot safely be created by the normal Terraform deployment before Terraform itself has remote state and GitHub has an AWS trust path.

The template creates:

- a dedicated encrypted/versioned/private S3 Terraform state bucket;
- a GitHub Actions OIDC provider for `token.actions.githubusercontent.com`, or reuses an existing provider ARN;
- a staging deployment IAM role trusted only by the ApplyAI GitHub `staging` environment;
- the permissions required by the current staging Terraform and release workflow.

Use a dedicated non-production AWS account for staging. The bootstrap deployment role is intentionally capable of creating the VPC, ALB, ECS, ECR, Aurora, S3, SQS, CloudWatch, EventBridge, IAM task roles, Route 53 integration, and Secrets Manager integration described by the deployment package.

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

Read the two values needed by GitHub:

```bash
aws cloudformation describe-stacks \
  --region us-east-1 \
  --stack-name applyai-staging-bootstrap \
  --query 'Stacks[0].Outputs' \
  --output table
```

Create a GitHub environment named `staging`, then set these **environment variables**:

```text
AWS_DEPLOY_ROLE_ARN=<GitHubDeployRoleArn output>
TF_STATE_BUCKET=<TerraformStateBucketName output>
AWS_REGION=us-east-1
```

The deployment workflows use GitHub OIDC (`id-token: write`) and do not require `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` secrets.

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

- deployment branches restricted to `main` (or temporarily the milestone branch during staging bring-up);
- required reviewer approval for infrastructure apply/release if desired;
- no long-lived AWS credentials;
- environment values listed in `docs/AWS_STAGING_DEPLOYMENT.md`.

The OIDC trust is scoped to the `staging` environment subject rather than all workflow runs in the repository. The template accepts both the conventional GitHub OIDC subject form and the newer immutable owner/repository-ID form.
