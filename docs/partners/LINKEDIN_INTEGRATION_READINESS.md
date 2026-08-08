# LinkedIn Integration Readiness

Updated: 2026-08-08

## Status

- Provider: LinkedIn
- ApplyAI partner access status: `NOT_REQUESTED`
- Repository integration readiness: `PREPARED`
- LinkedIn production approval: `NOT VERIFIED`
- Credentials: `NOT PROVISIONED`
- Job retrieval permission: `NOT GRANTED / NOT VERIFIED`
- Job storage permission: `NOT GRANTED / NOT VERIFIED`
- Redistribution permission: `NOT GRANTED / NOT VERIFIED`

ApplyAI must not infer data rights from public documentation, an accessible page, or the existence of a LinkedIn API product.

## Current official integration direction

The currently documented LinkedIn Talent Solutions path for new job integrations is Apply Connect / approved Talent Solutions partner access. The legacy Job Posting API documentation describes an approved-partner integration for posting and managing jobs on LinkedIn and states that new Job Posting API partnerships are not currently being accepted in favor of Apply Connect.

Official documentation references:

- https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview
- https://learn.microsoft.com/en-us/linkedin/talent/apply-connect/overview

These references must be re-verified during partner onboarding because provider products and terms can change.

## ApplyAI requested capability

ApplyAI's desired capability must be stated explicitly during partner discussions. Potential capabilities are modeled independently:

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

All are fail-closed until a reviewed agreement grants them.

## ApplyAI architecture presented to LinkedIn

ApplyAI is an employer-origin-first career platform. Its canonical job catalog prefers:

1. ApplyAI first-party employer jobs
2. employer official APIs / ATS job boards
3. employer JSON-LD / career pages
4. government official sources
5. authorized/licensed partner feeds

LinkedIn integration is therefore additive; ApplyAI does not depend on anonymous LinkedIn scraping.

The partner adapter boundary already supports provider-specific access mode, credentials, contractual rights, provenance, retention, attribution, source authority and non-owned remote-display semantics.

## Product and lifecycle capabilities

ApplyAI can support job lifecycle semantics such as:

```text
create
update
close
renew/reopen
application handoff
provider attribution
source provenance
```

Provider-specific behavior must follow the agreement and official API contract.

## Security and privacy package

Partner review materials should include:

- authentication and secret-storage architecture
- least-privilege worker credentials
- encrypted transport
- private runtime services where applicable
- candidate-data isolation
- auditability
- data-retention controls
- deletion workflows
- rate-limit handling
- retry/DLQ behavior
- provider attribution
- no credential or resume-body logging

## Onboarding checklist

```text
[ ] identify exact LinkedIn product/program
[ ] submit/prepare Talent Solutions partner request
[ ] document requested capabilities
[ ] execute applicable API/data agreement
[ ] record storage/redistribution/display rights
[ ] receive sandbox credentials if approved
[ ] mark partner status APPROVED_SANDBOX only after evidence
[ ] implement/configure only granted capabilities
[ ] run sandbox acceptance
[ ] receive production approval
[ ] mark APPROVED_PRODUCTION only after evidence
[ ] run staging acceptance
[ ] record attribution and retention obligations
```

## Non-goals

Do not implement:

- anonymous LinkedIn job crawling as a substitute for partner approval
- login/session automation
- CAPTCHA or anti-bot bypass
- cookie replay
- private API reverse engineering
- proxy rotation intended to evade controls

## Evidence required before claiming complete

LinkedIn is complete only when:

```text
partnership/access approved
+ agreement completed
+ credentials provisioned
+ exact granted capabilities recorded
+ sandbox/staging integration passes
```

Until then, provider status remains `PARTNERSHIP_REQUIRED`.