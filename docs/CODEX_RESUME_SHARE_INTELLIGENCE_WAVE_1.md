# CODEX IMPLEMENTATION CONTRACT — Resume Share Intelligence Wave 1

## Mission

Add privacy-first resume sharing and engagement intelligence to the existing ApplyAI candidate product. This wave is inspired only by publicly observable resume-sharing product behavior. It must be implemented clean-room with original models, scoring, code, UX, copy, and security boundaries.

## Product question

After a candidate sends a resume, ApplyAI should be able to answer:

> Did the smart link receive meaningful human engagement, what actions occurred, and which application or outreach channel did that engagement belong to?

The answer is an engagement signal, not a hiring probability and not verified recruiter identity.

## Wave 1 scope

### Smart resume links

- candidate-owned unguessable public tokens
- generic, job-linked, or application-linked links
- optional channel labels such as application, email, LinkedIn, referral, or networking
- current-resume mode or a pinned resume version
- candidate-controlled download permission
- optional expiry
- revoke/reactivate/delete
- no search indexing for public resume pages

### Public resume experience

- clean `/r/{token}` presentation
- inline PDF view where the browser supports it
- secure file open/download through an explicit public API allowlist
- visible privacy disclosure
- no raw candidate storage URL exposed

### Privacy-preserving analytics

- per-link random client session ID
- server stores only a SHA-256 session pseudonym scoped to that share link
- raw IP is not persisted
- no cross-link browser fingerprint
- no inferred viewer/company identity in Wave 1
- link-preview/crawler user agents are marked as suspected bots and excluded from human metrics
- event types: view, dwell, page scroll, file/link click, copy, download

### Candidate intelligence

- total views
- unique anonymous viewers
- returning viewers
- downloads
- clicks/copies
- suspected-bot count
- per-session dwell and scroll depth
- activity timeline
- CSV export
- deterministic engagement score and intent band:
  - `BROWSED`
  - `ENGAGED`
  - `DEEP_READ`

The score is an original ApplyAI engagement heuristic derived only from observed events. UI and API copy must not call it an employer score, recruiter score, application probability, interview probability, or hiring probability.

### Workflow integration

- `/resume` gets a **Share & track** entry point
- `/resume/signals` becomes the owner dashboard/outbox
- job detail gets **Create tracked resume link** with role context prefilled
- existing ApplyAI notifications receive first-view, return-view, and first-download events
- links reuse existing `Resume`, `ResumeVersion`, `Job`, `Application`, and `Notification` records

## Security boundaries

- normal `/api/backend` remains authenticated
- public browser requests use a separate `/api/public-backend` route with a strict path allowlist limited to resume-share public endpoints
- public proxy forwards no Clerk/session credentials
- public POST body is capped
- public tokens are high entropy
- revoked/expired links fail closed
- storage keys and private S3 URLs are not exposed
- owner APIs are user scoped
- public pages are `noindex`

## Clean-room boundary

Do not copy or extract ResumeShareIQ source code, prompts, private APIs, internal scoring, browser code, analytics implementation, protected text, or proprietary assets. Do not crawl authenticated/private pages or evade technical controls. Public product behavior may be used only to understand the problem space.

## Explicitly deferred

- company detection from IP addresses
- approximate IP geolocation
- raw IP retention
- third-party browser fingerprinting
- named viewer identification
- cross-link identity graphs
- hidden tracking disclosures
- true PDF page-by-page heat maps
- rewriting downloaded PDFs to inject tracked links
- QR generation
- push/mobile share dashboard
- daily email digest delivery provider integration
- voice-to-text feedback
- public API keys

These require separate privacy, accuracy, or product decisions.

## Verification gate

Before this wave is ready to merge:

- `pnpm lint`
- `pnpm --dir apps/web typecheck`
- `pnpm test:web`
- `pnpm build`
- `pnpm openapi:check`
- API Alembic upgrade/check
- API test suite
- API production container build
- candidate Playwright journey
- workflow validation
- staging Terraform validation

No merge or production deployment is part of this implementation wave unless explicitly requested.
