# ApplyAI staging environment configuration

This document is the source-of-truth contract for the GitHub `staging` environment. It contains examples only. Never commit real credentials, Clerk secrets, database passwords, candidate data, or private provider endpoints.

## Protection and identity

Configure the GitHub environment named `staging` with deployment branches restricted to `main` after bring-up. A temporary staging branch may be allowed only during reviewed setup. Require reviewer approval for apply, release, rollback, and destructive recovery operations when practical.

AWS authentication must use GitHub OIDC. Do not configure `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`.

The bootstrap role trust policy must accept only the ApplyAI repository and the `staging` environment subject.

## GitHub environment variables

| Variable | Required | Classification | Example shape | Source | Validation |
|---|---:|---|---|---|---|
| `AWS_REGION` | Yes | Non-secret | `us-east-1` | AWS staging account | Must match the ALB, ACM certificate, ECS, ECR, Aurora and Terraform backend region. |
| `AWS_DEPLOY_ROLE_ARN` | Yes | Non-secret | `arn:aws:iam::123456789012:role/applyai-staging-github-deploy` | CloudFormation bootstrap output | Must be assumable through GitHub OIDC from the `staging` environment. |
| `TF_STATE_BUCKET` | Yes | Non-secret | `applyai-terraform-state-123456789012-us-east-1` | CloudFormation bootstrap output | Bucket must exist, block public access, use encryption and have versioning enabled. |
| `WEB_ORIGIN` | Yes | Non-secret | `https://staging.applyai.example` | Vercel staging project | HTTPS origin only; must exactly match credentialed CORS configuration. |
| `API_BASE_URL` | Yes | Non-secret | `https://api.staging.applyai.example` | DNS configuration | HTTPS only; `/health` and `/ready` must resolve after release. |
| `API_CERTIFICATE_ARN` | Yes | Non-secret | `arn:aws:acm:us-east-1:123456789012:certificate/...` | ACM | Certificate must be `ISSUED`, cover the API hostname and exist in `AWS_REGION`. |
| `CLERK_ISSUER` | Yes | Non-secret | `https://example.clerk.accounts.dev` | Clerk staging application | HTTPS; OIDC discovery endpoint must be reachable. |
| `CLERK_JWKS_URL` | Yes | Non-secret | `https://example.clerk.accounts.dev/.well-known/jwks.json` | Clerk staging application | HTTPS; response must contain signing keys with `kid` and `kty`. |
| `CLERK_AUDIENCE` | Yes | Non-secret | `applyai-staging-api` | Clerk staging JWT template/application | Must be non-empty and match the API token audience policy. |
| `GREENHOUSE_BOARD_TOKENS` | Yes | Non-secret | `["company-one"]` | Reviewed public ATS source list | JSON array, maximum five unique non-empty identifiers during initial staging. |
| `LEVER_SITE_NAMES` | Yes | Non-secret | `["company-two"]` | Reviewed public ATS source list | JSON array, maximum five unique non-empty identifiers during initial staging. |
| `ASHBY_BOARD_NAMES` | Yes | Non-secret | `["company-three"]` | Reviewed public ATS source list | JSON array, maximum five unique non-empty identifiers during initial staging. |

At least one reviewed ATS source must be configured before the real staging preflight succeeds. Initial staging should contain one or two sources per provider, not a large crawl.

## Vercel staging values

Store these in the Vercel staging project rather than GitHub source:

| Variable | Required | Classification | Validation |
|---|---:|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Public runtime configuration | Must belong to the Clerk staging application. |
| `CLERK_SECRET_KEY` | Yes | Secret | Store only in Vercel encrypted environment settings. |
| `APPLYAI_API_URL` | Yes | Non-secret | Must equal `API_BASE_URL`. |
| `APP_ENV` | Yes | Non-secret | Must be `staging`. |
| `DEV_AUTH_ENABLED` | Yes | Non-secret | Must be `false`. |
| `DEV_AUTH_SECRET` | No | Secret | Must be absent/empty in staging. |

## Candidate acceptance identities

Create two non-production Clerk identities:

- Candidate A: executes the complete resume, profile, saved-job and application flow.
- Candidate B: verifies direct backend isolation from Candidate A resources.

Do not store their passwords or session tokens in the repository or workflow summaries.

## Reviewed source policy

Only use public employer or official ATS endpoints. Do not ingest from LinkedIn or Indeed copies, bypass authentication, defeat CAPTCHAs, rotate proxies to avoid controls, or access private endpoints.

Record each approved source in the staging acceptance report with provider, public URL, source identity, company mapping and reviewer decision.

## Validation order

1. Deploy/verify the CloudFormation bootstrap.
2. Configure the GitHub `staging` environment.
3. Configure Clerk and Vercel staging.
4. Run `ApplyAI Staging Preflight`.
5. Run `ApplyAI Staging Infrastructure` in `plan` mode.
6. Review the uploaded Terraform plan artifact.
7. Apply the dormant foundation only after the plan is approved.
8. Configure DNS/TLS.
9. Run the V2 release with source dispatch disabled.
10. Execute manual provider and failure-recovery acceptance before enabling the dispatcher.
