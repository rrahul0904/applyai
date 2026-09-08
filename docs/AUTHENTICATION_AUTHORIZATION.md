# Authentication and Authorization

## Current authentication boundary

Clerk is the identity provider. The Next.js application uses `ClerkProvider`,
Clerk middleware, and Clerk account components when keys are configured.

The FastAPI service:

1. Reads the Clerk bearer session token.
2. Fetches the Clerk JWKS key.
3. Verifies RS256 signature, issuer, time claims, and optional audience.
4. Requires `sub` and an authenticated `email` claim.
5. Maps `sub` to the unique `users.clerk_user_id`.
6. Creates the internal UUID user on the first authenticated API request.

The Clerk session token must include the verified primary email claim. Production
may later synchronize profile updates through signed Clerk webhooks.

## Current authorization rules

- Candidate endpoints never accept a client-provided `user_id`.
- Profile queries use the authenticated internal UUID.
- Resume queries filter by candidate ownership.
- Saved jobs use the authenticated UUID.
- Application reads and mutations require both application ID and owner UUID.
- Cross-user access returns `404` to avoid resource disclosure.
- Operations endpoints accept either:
  - a Clerk-authenticated operator whose email is present in the API-side
    `APPLYAI_OPERATOR_EMAILS` allowlist, or
  - the backend-only `X-ApplyAI-Internal-Token` service credential.
- Production Vercel does not require the internal service token or operator allowlist.

Automated tests prove User B cannot retrieve User A's profile or resume and
cannot retrieve or modify User A's application. Operator tests prove non-operators
are denied and missing operator configuration fails closed.

## Cross-provider Clerk configuration contract

The public web publishable key and the FastAPI Clerk issuer must belong to the same
Clerk instance. Both tiers independently hash the normalized Clerk instance hostname
and expose only a short SHA-256 fingerprint through readiness. Production readiness
requires the fingerprints to match.

This prevents a partial credential change (for example, replacing only the Vercel
publishable/secret pair while Railway still verifies tokens against another Clerk
instance) from producing a false green release state.

## Production readiness

The backend, worker, database, migrations, operator policy, and real job-supply
acceptance are activated. Full production authentication remains fail-closed until
the authorized Clerk production instance is configured with matching live credentials:

### Vercel
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...`
- `CLERK_SECRET_KEY=sk_live_...`
- `APPLYAI_API_URL` points to the verified Railway API
- `DEV_AUTH_ENABLED=false`

### Railway API
- `AUTH_PROVIDER=clerk`
- `CLERK_ISSUER` for the same production instance
- `CLERK_JWKS_URL` for the same production instance
- optional `CLERK_AUDIENCE`
- `APPLYAI_OPERATOR_EMAILS` backend-side operator allowlist

`/api/readiness` must report `production_ready=true`,
`clerk_instance_match=true`, and `operator_auth_location="api"`.

## Production auth acceptance

After the live Clerk pair is configured, run the GitHub Actions workflow
**Production Clerk Auth Acceptance**. Supply the optional `operator_email` workflow input
with an existing Clerk production user that is present in the Railway API operator allowlist
to include live Operations-control-plane authorization in the same run.

The workflow:

1. Fails closed unless both configured keys use live Clerk prefixes.
2. Requires production readiness before attempting browser authentication.
3. Reads the live Clerk environment to understand enabled/required user attributes.
4. Creates a temporary verified Clerk user through the Clerk Backend API.
5. Creates a short-lived one-time sign-in token.
6. Redeems the token in Chromium against the real production deployment.
7. Verifies the authenticated browser can load the candidate application and call
   `/api/backend/me`, proving browser → Next.js → FastAPI → Clerk verification.
8. When `operator_email` is supplied, resolves exactly one existing Clerk user, issues a
   separate one-time ticket, and verifies `/admin/operations` through API-side operator authorization.
9. Deletes only the temporary candidate Clerk user in an `always()` cleanup step; the existing
   operator account is never modified or deleted.

The one-time ticket is masked in GitHub Actions and is never committed or printed.

After that workflow passes, run **Production Provider Readiness** and perform the
post-deploy Vercel runtime-error scan. The historical `secret-key-invalid` cluster
must not recur after the cutover.

## Future employer authorization

Employer resources will require an `organization_members` row and server-side
role checks for Owner, Admin, Recruiter, or Hiring Manager. A token claim alone
will never grant organization access.
