# ApplyAI Career-Site Discovery and Public Job URL Import

## Scope

This layer reuses Job Source Platform V1 and discovers where employers already publish jobs without requiring an ApplyAI employer account.

Implemented flows:

```text
Operator company domain
    -> bounded career-site discovery
    -> robots decision
    -> ATS fingerprint
    -> source registry
    -> scheduled ATS ingestion when supported

Candidate public job URL
    -> safe validation
    -> durable discovery record + transactional outbox
    -> background task worker
    -> robots decision
    -> ATS fingerprint
    -> JobPosting JSON-LD or conservative HTML extraction
    -> validation/dedup
    -> canonical job
```

No browser automation, CAPTCHA bypass, proxy rotation, login bypass, private endpoint access, or anti-bot circumvention is implemented.

## Security boundary

`SafeHttpFetcher` accepts only HTTP and HTTPS.

It rejects:

- localhost;
- literal private, loopback, link-local, reserved and metadata-service addresses;
- DNS names resolving to any non-public address;
- `.local` and `.internal` names;
- credential-bearing URLs;
- file/FTP and other schemes.

Every redirect target is revalidated before it is requested.

Crawl budgets cap:

- pages per discovery;
- decompressed response bytes;
- redirects;
- request duration.

Generic pages are fetched as HTML/text only. JavaScript is not executed.

## Robots access policy

Each target receives an explicit decision:

```text
ALLOWED
DISALLOWED
UNKNOWN
MANUAL_REVIEW
```

A robots disallow becomes a terminal BLOCKED discovery. Authentication/forbidden responses require manual review. ApplyAI does not retry by attempting to evade the restriction.

## Bounded company discovery

For one company root URL, discovery may inspect:

```text
/careers
/jobs
/careers/jobs
/company/careers
/work-with-us
/join-us
```

It also examines semantic homepage links such as “Careers,” “Jobs,” “Join our team,” and “Open positions.” External links are followed only when they match a known recruiting-provider signal.

The crawler does not traverse the entire company website.

## ATS fingerprinting

Detection uses evidence from:

- current/resolved URL;
- links;
- script sources;
- iframe sources;
- metadata;
- known public endpoint hostnames.

Recognized platforms include:

- Greenhouse;
- Lever;
- Ashby;
- Workday;
- SmartRecruiters;
- Workable;
- iCIMS;
- Oracle Recruiting;
- SAP SuccessFactors;
- Jobvite/UKG evidence signals;
- conservative custom career sites.

A detection contains provider, confidence, evidence, candidate source URL, and source identity. Uncertain detections remain disabled/manual rather than treated as implemented adapters.

High-confidence Greenhouse, Lever and Ashby detections register enabled V1 sources. Other detected platforms register disabled source records until a dedicated connector exists.

## Sitemap discovery

Discovery checks bounded sitemap candidates from:

- robots `Sitemap:` declarations;
- `/sitemap.xml`;
- `/sitemap_index.xml`;
- `/jobs-sitemap.xml`.

Only a small number of sitemap documents are parsed. URLs are candidates—not assumed jobs—when their paths contain job/career/position/opening patterns.

## Extraction priority

```text
official ATS API
    -> JobPosting JSON-LD
    -> provider-specific structured data
    -> conservative generic HTML
```

Prompt 2 implements the JSON-LD and conservative HTML layers. Supported official ATS boards continue through Prompt 1 adapters.

### JobPosting JSON-LD

Preserved fields include:

- title;
- description;
- datePosted;
- validThrough;
- employmentType;
- hiringOrganization;
- jobLocation;
- applicantLocationRequirements;
- jobLocationType;
- baseSalary;
- identifier;
- directApply metadata;
- original JSON-LD node.

### Generic extraction

Generic HTML is accepted only when it looks like one specific job:

- exactly one meaningful H1;
- exactly one apply link;
- substantial job-specific content;
- optional requisition/location evidence.

Pages with many apply links, several JobPosting nodes, insufficient content, or weak identity are QUARANTINED and remain non-searchable.

## Candidate URL import API

```text
POST /api/v1/jobs/import-url
GET  /api/v1/jobs/import-url/{discovery_id}
```

POST performs only URL/security validation and the database transaction. It creates:

- `job_source_discoveries` row;
- `JOB_URL_IMPORT` outbox event.

The response is HTTP 202 with a durable status ID. Fetching/extraction occurs in the background worker.

Imports are idempotent by candidate + canonical submitted URL. A candidate cannot read another candidate’s import status.

## Company discovery operations

Protected operator routes:

```text
POST /api/v1/internal/job-source-discoveries
GET  /api/v1/internal/job-source-discoveries
GET  /api/v1/internal/job-source-discoveries/{id}
POST /api/v1/internal/job-source-discoveries/{id}/retry
```

They use the separate internal operator token and are excluded from the candidate OpenAPI SDK.

## Durable discovery record

`job_source_discoveries` stores:

- candidate/company/source/job links;
- input domain and URL;
- discovered/resolved/canonical/apply URLs;
- detected provider and confidence;
- status and access policy;
- evidence;
- ETag and Last-Modified;
- material content hash;
- attempts and non-sensitive errors;
- discovered/verified/completed timestamps.

Statuses used by the worker:

```text
QUEUED
FETCHING
DISCOVERED
VERIFIED
REJECTED
BLOCKED
FAILED
```

FAILED remains retryable and follows SQS/DLQ behavior. VERIFIED, DISCOVERED, REJECTED and BLOCKED are terminal/acknowledgeable.

## Queue routing

Prompt 2 keeps the existing SQS topology and routes by task type:

```text
RESUME_PARSE
JOB_URL_IMPORT
SOURCE_DISCOVERY
```

The deployed worker entrypoint now delegates discovery tasks rather than acknowledging them as unsupported. Prompt 3 may split ingestion/verification queues and capacity after measuring workload.

## Conditional retrieval

Discovery records retain ETag, Last-Modified, and content hash. Reprocessing sends conditional headers when available and avoids re-extracting unchanged 304 responses.

## Observability

Structured events include:

- `career_discovery_started` / worker receipt through durable task state;
- `career_source_detected`;
- `career_source_registered`;
- `career_discovery_failed`;
- `career_discovery_blocked`;
- `job_url_imported`;
- `job_url_rejected`.

Events contain IDs/provider/status—not full HTML, credentials, tokens or complete descriptions.

## Tests

Fixtures cover:

- public URL acceptance;
- localhost/private/link-local/metadata rejection;
- redirect-to-private rejection;
- response byte budget;
- robots allow/disallow;
- ATS fingerprints;
- bounded sitemap filtering;
- JobPosting JSON-LD;
- listing-page quarantine;
- transactional outbox creation;
- import idempotency/user isolation;
- background canonical job creation;
- company source registration;
- worker terminal idempotency.

No discovery test depends on live internet availability.

## Deferred to Prompt 3

- dedicated source-dispatch/ingestion queues and independent worker scaling;
- adaptive source scheduling based on measured change rate;
- apply-link verification service;
- source authority/field conflict selection;
- quality KPI service;
- synthetic 10K/50K/250K search measurements;
- cost telemetry and AWS ingestion alarms.
