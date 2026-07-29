# Authentication and Authorization

## CURRENT authentication boundary

Clerk is the identity provider. The Next.js application uses `ClerkProvider`,
Clerk middleware, and Clerk account components when keys are configured.

The FastAPI service:

1. Reads the bearer session token.
2. Fetches the Clerk JWKS key.
3. Verifies RS256 signature, issuer, time claims, and optional audience.
4. Requires `sub` and an authenticated `email` claim.
5. Maps `sub` to the unique `users.clerk_user_id`.
6. creates the internal UUID user on the first authenticated API request.

The Clerk session token must include the verified primary email claim. Production
may later synchronize profile updates through signed Clerk webhooks.

## CURRENT authorization rules

- Candidate endpoints never accept a client-provided `user_id`.
- Profile queries use the authenticated internal UUID.
- Resume queries filter by candidate ownership.
- Saved jobs use the authenticated UUID.
- Application reads and mutations require both application ID and owner UUID.
- Cross-user access returns `404` to avoid resource disclosure.

Automated tests prove User B cannot retrieve User A's profile or resume and
cannot retrieve or modify User A's application.

## Configuration status

Code and tests are complete for the identity boundary. Live sign-in is BLOCKED
until Clerk publishable/secret keys, issuer, JWKS URL, and email claim are
configured. Google must be enabled in the Clerk dashboard alongside email.

## Future employer authorization

Employer resources will require an `organization_members` row and server-side
role checks for Owner, Admin, Recruiter, or Hiring Manager. A token claim alone
will never grant organization access.
