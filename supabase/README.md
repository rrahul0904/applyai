# ApplyAI Supabase configuration

ApplyAI keeps Alembic as the canonical application-schema migration system. Supabase-specific
platform policies live in this directory because they reference the hosted `auth` and
`storage` schemas that do not exist in ordinary PostgreSQL clean-room environments.

Production activation order:

1. Create the dedicated ApplyAI Supabase project.
2. Set its database connection as the migration target.
3. Run `alembic upgrade head && alembic current && alembic heads && alembic check`.
4. Apply `supabase/policies.sql` through the Supabase migration tool.
5. Run Supabase security/performance advisors.
6. Generate server-only Storage S3 credentials and configure the API.
7. Configure the web publishable key and project URL.
8. Create/verify an operator user, provision the ApplyAI user record, then add the
   `operator` role in `user_roles`.
9. Run real auth, Storage, RLS, API, job-supply and scale acceptance before removing the
   Clerk/Railway compatibility path.

Candidate business tables intentionally remain FastAPI-only. RLS plus privilege revocation
prevents the Supabase Data API from bypassing FastAPI business authorization. Supabase Storage
uses authenticated RLS policies because direct signed/user-scoped object access is an intended
storage capability.
