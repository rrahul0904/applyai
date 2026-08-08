# Indeed Integration Readiness

Updated: 2026-08-08

## Status

- Provider: Indeed
- ApplyAI partner access status: `NOT_REQUESTED`
- Repository integration readiness: `PREPARED`
- Indeed production approval: `NOT VERIFIED`
- Credentials: `NOT PROVISIONED`
- Catalog retrieval permission: `NOT GRANTED / NOT VERIFIED`
- Job storage permission: `NOT GRANTED / NOT VERIFIED`
- Redistribution permission: `NOT GRANTED / NOT VERIFIED`
- Remote-display permission: `NOT GRANTED / NOT VERIFIED`

ApplyAI must not infer provider data rights from public job visibility or the existence of an Indeed API/product.

## Current official integration products to evaluate

Indeed documents separate partner capabilities. They must not be collapsed into one generic switch.

### Job Sync

The Job Sync API is an approved partner integration for creating, updating and expiring jobs on Indeed. It is not assumed to grant unrestricted retrieval/storage of Indeed's marketplace catalog.

Reference:

- https://docs.indeed.com/job-sync-api

### Publisher/search experience

Indeed also documents publisher integration for displaying a subset of Indeed/Indeed PLUS jobs on an approved partner site. Where the agreement is display-only, ApplyAI must treat results as provider-controlled remote display rather than copying the catalog into the canonical owned database.

Reference:

- https://docs.indeed.com/indeed-plus/publisher-js-plugin

### Partner Console

Provisioned products, credentials and approval state are managed through Indeed's partner process / Partner Console.

Reference:

- https://docs.indeed.com/getstarted/partner-console

All provider documentation must be re-verified during onboarding.

## Capability separation

Model Indeed capabilities independently:

```text
INDEED_JOB_SYNC
INDEED_PUBLISHER_SEARCH
INDEED_AUTHORIZED_FEED
```

Contract rights must be recorded independently:

```text
can_search
can_ingest
can_store
can_redistribute
can_display_remote
can_apply
can_post
can_update
can_close
retention_policy
attribution_required
```

All rights remain false until reviewed provider approval/contract evidence grants them.

## Owned catalog vs remote display

ApplyAI must distinguish:

```text
CATALOG_OWNED_JOB
REMOTE_DISPLAY_ONLY_JOB
```

A provider-approved display/search integration does not automatically grant permission to persist or redistribute the provider's job catalog.

For remote-display-only access:

- preserve required attribution
- link/apply according to provider terms
- avoid canonical data ownership claims
- respect retention restrictions
- do not use remote display results as authoritative closure evidence for employer-origin canonical jobs

## ApplyAI architecture presented to Indeed

ApplyAI's primary catalog is employer-origin-first:

1. ApplyAI first-party employers
2. official ATS/public employer APIs
3. employer structured career pages
4. government/public-sector sources
5. authorized/licensed feeds

Indeed is an additive partner channel, not a dependency that justifies unauthorized crawling.

## Security / onboarding package

Prepare:

- product and user-flow description
- publisher/job-board use case
- ATS/job-sync use case if relevant
- authentication/OAuth handling
- secret storage
- rate-limit/retry behavior
- attribution design
- outbound-link behavior
- data-storage/retention controls
- privacy/security architecture
- logging controls
- provider reporting/measurement requirements

## Onboarding checklist

```text
[ ] identify exact Indeed partner service(s)
[ ] prepare/submit partner application
[ ] document requested capabilities
[ ] receive provider review outcome
[ ] execute applicable contract/license terms
[ ] record catalog ownership/storage/display rights
[ ] receive credentials through approved channel
[ ] mark APPROVED_SANDBOX only after evidence
[ ] configure only the granted capabilities
[ ] run sandbox/provider acceptance
[ ] receive production approval
[ ] run ApplyAI staging acceptance
[ ] record attribution and retention obligations
```

## Non-goals

Do not implement:

- anonymous Indeed crawling as a substitute for partner access
- CAPTCHA/anti-bot bypass
- login/session circumvention
- proxy rotation intended to evade controls
- undocumented private API use

## Evidence required before claiming complete

Indeed is complete only when:

```text
applicable partnership approved
+ partner service provisioned
+ credentials issued
+ permitted storage/display/redistribution behavior documented
+ staging integration passes
```

Until then, provider status remains `PARTNERSHIP_REQUIRED`.