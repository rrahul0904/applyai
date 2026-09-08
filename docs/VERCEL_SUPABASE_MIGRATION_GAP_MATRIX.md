# ApplyAI Vercel + Supabase migration gap matrix

This file is a live implementation inventory, not a substitute for implementation.

## Provider foundation

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| Supabase organization access | complete | Authorized Supabase integration can list projects and organizations. |
| Dedicated ApplyAI Supabase project | blocked | Project creation was attempted. The connected account is already at the maximum two active Free projects. Do not repurpose another product without explicit authorization. |
| Vercel web project | complete | Existing ApplyAI Vercel project and Git previews are operational. |
| Vercel FastAPI project/runtime | needs migration | Vercel supports FastAPI/Python; dedicated API deployment and production parity are not yet activated. |
| Railway compatibility runtime | already compatible | Kept temporarily so the product remains available during migration. Must be decommissioned only after Vercel/Supabase parity. |
| Clerk compatibility identity | already compatible | Kept temporarily for the existing deployment. Must be removed only after Supabase Auth production acceptance. |

## Database and identity

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| PostgreSQL application schema | already compatible | ApplyAI already uses PostgreSQL + Alembic. |
| Provider-neutral user identity | complete | Internal ApplyAI UUID preserved; nullable legacy Clerk ID plus Supabase `auth_user_id` and `auth_provider` added. |
| Identity migration | needs migration | Production row migration waits for the dedicated Supabase database. Safe email-based linking is implemented only when exactly one existing account matches. |
| Database roles | complete in code | `roles` and `user_roles` added with candidate/operator/admin seed roles. |
| Alembic migration | complete in code | `o5g9k1d4h642_supabase_identity_roles.py` follows the Operations certification head. Must be applied and drift-checked on Supabase. |
| Production data copy | blocked | Requires dedicated Supabase database. Preserve the accepted Open Jobs inventory and legitimate candidate data. |
| Row-count parity report | blocked | Generated only after source → Supabase copy. |

## Authentication and authorization

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| FastAPI Supabase JWT verifier | complete in code | Public JWKS verification, issuer/audience validation, email claim requirement, provider-neutral claims. |
| Web email/password auth | complete in code | Server-side Supabase Auth HTTP flow with persistent session cookies. |
| Google OAuth | complete in code | PKCE verifier/challenge/state flow with Supabase provider authorize endpoint and one-time auth-code exchange. |
| Session refresh | complete in code | Next proxy refreshes expiring access tokens using the refresh token. |
| Web → FastAPI bearer forwarding | complete in code | API proxy forwards the current Supabase or transitional Clerk bearer token. |
| Supabase project consistency | complete in code | Web/API expose and compare non-secret project fingerprints. |
| Operator authorization | complete in code | Supabase path requires database `operator`/`admin` role; legacy email allowlist is not trusted for Supabase identities. |
| Real Supabase signup/sign-in/logout | blocked | Requires dedicated project and provider activation. |
| Google provider activation | blocked | Requires dedicated project and Google OAuth credentials/redirect configuration. |
| Production auth E2E | blocked | Requires live Supabase project. |

## Storage

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| Supabase Storage adapter | complete in code | Existing object-storage abstraction now supports Supabase Storage's S3-compatible server endpoint. |
| Resume key compatibility | complete | Existing `candidate/{internal-user-uuid}/resume/...` keys are preserved. |
| Private resumes bucket | complete as policy | `supabase/policies.sql` creates/forces private `resumes` bucket. |
| Storage ownership RLS | complete as policy | `auth.uid()` maps through `users.auth_user_id` to the internal UUID encoded in object paths. |
| Live bucket/credentials | blocked | Requires dedicated Supabase project. |
| Resume upload/download/delete acceptance | blocked | Run against Supabase Storage after activation. |

## RLS and database security

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| Candidate Data API boundary | complete as policy | Candidate tables enable RLS and revoke direct anon/authenticated business-table access. FastAPI remains canonical authorization boundary. |
| Self identity/role policies | complete as policy | Authenticated users may read only their own ApplyAI identity/role mapping. |
| Storage RLS | complete as policy | Private resume object select/insert/update/delete policies are user-owned. |
| Live policy application | blocked | Requires dedicated project. |
| Supabase advisors | blocked | Run security/performance advisors after live DDL/policies are applied. |

## Durable work

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| PostgreSQL task queue | already compatible | Existing queue, leases, retries, idempotency and outbox are PostgreSQL-native. |
| Supabase Postgres queue target | needs migration | Database connection must move to Supabase. |
| Railway worker | already compatible | Temporary migration runtime only. |
| Vercel bounded worker replacement | needs migration | Implement bounded task drain via Vercel execution; no infinite serverless loop. |
| Source scheduler | needs migration | Preserve semantics and rerun 1k/10k/50k benchmarks. |
| Browser automation | needs migration | Must be explicitly certified on a supported browser runtime before Railway is removed. |

## Readiness and operations

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| Provider-neutral API readiness | complete in code | Reports DB, auth provider, operator mode, storage, internal auth and provider fingerprints without secrets. |
| Provider-neutral web readiness | complete in code | Supports Supabase-first readiness with transitional Clerk fallback. |
| Operations control plane | already compatible | Existing Jobs/Sources/Ingestion/Certification surface retained. |
| Supabase operational cards | needs migration | Add DB/auth/storage/queue/worker readiness after provider activation. |

## CI/CD and release

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| Existing exact-head CI | in progress | Current branch reruns full API/web/E2E/scale/clean-room matrix after each migration commit. |
| Supabase migration validation | needs migration | Add live/local Supabase policy/auth/storage validation gate. |
| Vercel API deployment workflow | needs migration | Add dedicated FastAPI Vercel deployment and health/readiness proof. |
| Supabase production auth acceptance | needs migration | Replace Clerk production workflow after live Supabase project is available. |
| Railway deployment removal | blocked | Remove only after Vercel API + bounded worker parity. |
| Clerk workflow removal | blocked | Remove only after Supabase Auth E2E passes. |

## Dependency-removal gates

The migration is not complete until both commands have no runtime/config dependencies beyond
explicit historical migration notes:

```bash
rg -i "clerk"
rg -i "railway"
```

Neither provider will be removed early merely to make those searches look clean.
