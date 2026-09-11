# Supabase production operator bootstrap

ApplyAI production intentionally stores operator/admin authorization in the application database. Supabase Auth proves identity; it does not grant ApplyAI privileges.

The production readiness contract stays fail-closed until at least one active ApplyAI user has an `operator` or `admin` row in `user_roles`.

## Security boundary

Do not grant operator/admin from Supabase `user_metadata`, email-domain rules, first-user-wins logic, or a client-side environment variable. `user_metadata` is user-editable and is not an authorization source.

The bootstrap command only promotes a user who:

- already exists in ApplyAI `users`;
- already has a non-null `auth_user_id`;
- is linked with `auth_provider='supabase'`;
- has an active ApplyAI account;
- resolves to exactly one normalized email match.

The command is idempotent and can only grant `operator` or `admin`.

## One-time production sequence

1. Sign in once through the production ApplyAI Supabase Auth flow using the intended operator email.
2. Reach any authenticated candidate route (for example `/dashboard`). The backend `/api/v1/me` path creates or safely links the corresponding ApplyAI `users` row.
3. In the production API/Railway runtime, run:

   ```bash
   cd services/api
   python -m scripts.bootstrap_operator \
     --email "$APPLYAI_PRODUCTION_OPERATOR_EMAIL" \
     --role admin
   ```

   Use `--role operator` instead when administrative privileges are not required.

4. Confirm the command reports `"ok": true`. Re-running the command is safe; `created_assignment` becomes `false` after the role already exists.
5. Check the production web readiness endpoint. It must return HTTP 200 with:

   ```json
   {
     "runtime_ready": true,
     "production_ready": true,
     "checks": {
       "auth_provider": "supabase",
       "supabase_instance_match": true,
       "operator_configured": true,
       "operator_auth_location": "database",
       "dev_auth_enabled": false
     }
   }
   ```

6. Run **Production Supabase Auth Acceptance** against the canonical production URL. The workflow verifies a real temporary candidate session, the existing operator session, FastAPI identity propagation, the Operations control plane, and final production readiness.
7. Review Vercel/API logs for authentication or authorization errors after the acceptance run.

## Failure behavior

The bootstrap command exits without granting access when the user has not signed in yet, the email is ambiguous, the user is not linked to Supabase, the account is inactive, or the requested role is not `operator`/`admin`.

Do not bypass these failures by inserting a placeholder operator row only to make `/api/readiness` green. Production readiness is intended to represent a usable operator path, not only a database condition.
