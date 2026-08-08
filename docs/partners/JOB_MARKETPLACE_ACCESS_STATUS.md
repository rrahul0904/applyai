# Job Marketplace Access Status

Updated: 2026-08-08

This document separates source-code readiness from provider approval and contractual rights. Public visibility is never treated as permission to crawl, store or redistribute job data.

## Blocker classes

```text
NO_BLOCKER
TECHNICAL_BLOCKER
AUTHENTICATION_BLOCKER
PARTNERSHIP_BLOCKER
CONTRACT_LICENSE_BLOCKER
DATA_STORAGE_RIGHTS_BLOCKER
PROVIDER_POLICY_BLOCKER
```

A provider may have more than one blocker.

## Partner approval states

```text
NOT_REQUESTED
APPLICATION_PREPARED
APPLICATION_SUBMITTED
UNDER_REVIEW
APPROVED_SANDBOX
APPROVED_PRODUCTION
REJECTED
SUSPENDED
```

Repository code must never promote a provider into an approved state without external evidence.

## Contract-right fields

Every provider integration can be evaluated independently for:

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

All partnership-gated providers default to no granted rights.

## Current provider matrix

| Provider | Current ApplyAI strategy | Partner status | Current blocker | Catalog retrieval/storage claim |
|---|---|---|---|---|
| Greenhouse | Public employer ATS | N/A | NO_BLOCKER for configured public boards | Employer-origin ingestion supported |
| Lever | Public employer ATS | N/A | NO_BLOCKER for configured public postings | Employer-origin ingestion supported |
| Ashby | Public employer ATS | N/A | NO_BLOCKER for configured public boards | Employer-origin ingestion supported |
| SmartRecruiters | Public employer posting interface | N/A | NO_BLOCKER for configured public postings | Employer-origin ingestion supported |
| USAJOBS | Official government API | N/A | AUTHENTICATION_BLOCKER until issued credentials configured | Official API connector implemented |
| ReliefWeb | Official API | N/A | AUTHENTICATION_BLOCKER until approved app identity/configuration exists | Official connector implemented |
| Workday | Employer career-site discovery / bounded structured extraction where allowed | N/A | provider/employer specific | No unrestricted Workday marketplace claim |
| Workable | Employer career-site discovery / bounded structured extraction where allowed | N/A | provider/employer specific | No unrestricted marketplace claim |
| iCIMS | Employer career-site discovery / bounded structured extraction where allowed | N/A | provider/employer specific | No unrestricted marketplace claim |
| Oracle Recruiting | Employer career-site discovery / bounded structured extraction where allowed | N/A | provider/employer specific | No unrestricted marketplace claim |
| SAP SuccessFactors | Employer career-site discovery / bounded structured extraction where allowed | N/A | provider/employer specific | No unrestricted marketplace claim |
| NEOGOV / GovernmentJobs | Detection + permitted public employer path | N/A | interface/policy review per source | No generic feed claim |
| LinkedIn | Approved Talent Solutions / Apply Connect path only | NOT_REQUESTED | PARTNERSHIP_BLOCKER + CONTRACT_LICENSE_BLOCKER + DATA_STORAGE_RIGHTS_BLOCKER | No LinkedIn catalog ingestion/storage rights claimed |
| Indeed | Approved partner product only | NOT_REQUESTED | PARTNERSHIP_BLOCKER + CONTRACT_LICENSE_BLOCKER + DATA_STORAGE_RIGHTS_BLOCKER | No unrestricted Indeed catalog ingestion/storage rights claimed |
| Dice | Authorized/licensed feed if contracted; otherwise employer-origin | NOT_REQUESTED | PARTNERSHIP_BLOCKER + CONTRACT_LICENSE_BLOCKER | No catalog rights claimed |
| Monster | Authorized/licensed feed if contracted; otherwise employer-origin | NOT_REQUESTED | PARTNERSHIP_BLOCKER + CONTRACT_LICENSE_BLOCKER | No catalog rights claimed |
| ZipRecruiter | Authorized/licensed feed if contracted; otherwise employer-origin | NOT_REQUESTED | PARTNERSHIP_BLOCKER + CONTRACT_LICENSE_BLOCKER | No catalog rights claimed |
| Glassdoor | Authorized/licensed feed if contracted; otherwise employer-origin | NOT_REQUESTED | PARTNERSHIP_BLOCKER + CONTRACT_LICENSE_BLOCKER | No catalog rights claimed |
| Wellfound | Employer/startup discovery input; jobs should resolve to authorized/original source | NOT_REQUESTED | PARTNERSHIP_BLOCKER where direct feed desired | No catalog rights claimed |
| Built In | Company discovery input; prefer employer-origin jobs | NOT_REQUESTED | PARTNERSHIP_BLOCKER where direct feed desired | No catalog rights claimed |
| Handshake | Authorized partner path only if contracted | NOT_REQUESTED | PARTNERSHIP_BLOCKER | No catalog rights claimed |
| HigherEdJobs | Prefer university-origin ATS/career source; feed only if authorized | NOT_REQUESTED | PARTNERSHIP_BLOCKER where direct feed desired | No catalog rights claimed |
| Idealist | Prefer nonprofit-origin source; feed only if authorized | NOT_REQUESTED | PARTNERSHIP_BLOCKER where direct feed desired | No catalog rights claimed |
| Devex | Authorized/licensed feed if contracted; otherwise organization-origin | NOT_REQUESTED | PARTNERSHIP_BLOCKER where direct feed desired | No catalog rights claimed |

## LinkedIn blocker record

```text
provider: LinkedIn
official product/integration identified: Talent Solutions / Apply Connect; legacy Job Posting API documentation retained for existing approved partners
current partner status: NOT_REQUESTED
requested capability: TO BE AGREED
credentials received: no
sandbox available: not verified
production approved: no
job retrieval permitted: not verified / not granted
job storage permitted: not verified / not granted
redistribution permitted: not verified / not granted
remote display permitted: not verified / not granted
attribution requirement: contract dependent
```

The technical partner adapter boundary can be prepared, but partner approval and exact data rights cannot be created in source code.

## Indeed blocker record

```text
provider: Indeed
official products identified: Job Sync; publisher/search partner experience; other contracted feeds only when provisioned
current partner status: NOT_REQUESTED
requested capability: TO BE AGREED
credentials received: no
sandbox available: not verified
production approved: no
job retrieval permitted: not verified / not granted
job storage permitted: not verified / not granted
redistribution permitted: not verified / not granted
remote display permitted: not verified / not granted
attribution requirement: contract/product dependent
```

Do not confuse Job Sync (posting/managing jobs on Indeed) with permission to ingest Indeed's marketplace into ApplyAI.

## Launch policy

LinkedIn and Indeed are not launch blockers for ApplyAI's employer-origin catalog. ApplyAI may launch from:

```text
ApplyAI first-party employers
+ Greenhouse
+ Lever
+ Ashby
+ SmartRecruiters
+ permitted employer career pages / JSON-LD
+ USAJOBS
+ ReliefWeb
+ universities
+ hospitals / health systems
+ nonprofits / NGOs
+ government organizations
+ authorized/licensed feeds
+ candidate imports
```

Provider partnerships should progress in parallel.

## Evidence rule

A provider can move to `APPROVED_SANDBOX` or `APPROVED_PRODUCTION` only when the corresponding approval, credentials and granted rights are recorded outside source-control assumptions and verified in staging. Provider secrets must never be committed.