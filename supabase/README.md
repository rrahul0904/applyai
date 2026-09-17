# ApplyAI Supabase configuration

ApplyAI keeps Alembic as the canonical application-schema migration system. Supabase-specific
platform policies live in this directory because they reference hosted `auth` and `storage`
schemas that do not exist in ordinary PostgreSQL clean-room environments.

Production activation order:

1. Create the dedicated ApplyAI Supabase project.
2. Set its database connection as the migration target when Supabase Postgres is the selected data plane.
3. Run `alembic upgrade head && alembic current && alembic heads && alembic check`.
4. Apply `supabase/policies.sql` through the Supabase migration tool.
5. Run Supabase security/performance advisors and require no ERROR-level Data API/RLS findings.
6. Generate server-only Storage S3 credentials when Supabase Storage is selected and configure the API.
7. Configure the web publishable key and project URL for Supabase Auth.
8. Create/verify an operator identity, let FastAPI provision/link the ApplyAI user record, then grant the database-backed `operator` or `admin` role through the reviewed bootstrap path.
9. Run real auth, Storage, RLS, API, job-supply and scale acceptance before removing compatibility infrastructure.

## Data API boundary

The **entire ApplyAI application schema is FastAPI-only by default**. `supabase/policies.sql`:

- enables RLS on every current table in `public`;
- revokes all table and sequence privileges from `anon` and `authenticated`;
- removes direct execution of public-schema functions from browser roles;
- removes PostgreSQL default grants so newly migrated public tables, sequences, and functions do not silently become Data API-accessible;
- keeps the identity lookup helper in a non-exposed `private` schema;
- grants only the explicitly required helper execution to `authenticated` for Storage RLS.

This is deliberate defense in depth. Browser application data requests go through FastAPI, where business authorization, auditing, and evidence boundaries live. Supabase Auth is the identity provider; it is not an alternate database API for ApplyAI business tables.

Supabase Storage is separate: when used, `storage.objects` receives explicit authenticated policies scoped to the candidate's internal ApplyAI user ID and the private `resumes` bucket.
