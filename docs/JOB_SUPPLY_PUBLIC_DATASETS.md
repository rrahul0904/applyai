# ApplyAI Job Supply — Public Organization Dataset Inputs

Updated: 2026-08-08

This document records authoritative/public dataset candidates for building the organization universe. These datasets are for organization discovery; ApplyAI should still source jobs from the employer's own ATS/career site or an authorized job feed whenever possible.

## U.S. public companies — SEC EDGAR

**Owner:** U.S. Securities and Exchange Commission

**Useful inputs:** SEC company ticker JSON plus EDGAR submissions metadata/bulk submissions.

**Why useful:** public-company names, ticker/CIK identities, aliases/former names and exchange metadata can seed a large employer universe without relying on a commercial ranking list.

**Access:** public SEC data APIs and bulk files; automated access must follow SEC fair-access/user-agent requirements.

**Recommended ApplyAI use:** build/import canonical company identities and domains where independently verified; do not treat SEC registration as proof of a careers URL or active hiring.

## U.S. colleges and universities — NCES IPEDS

**Owner:** U.S. Department of Education / National Center for Education Statistics

**Useful inputs:** IPEDS complete data files and institution directory fields.

**Why useful:** authoritative U.S. postsecondary institution universe covering universities, colleges and technical/vocational institutions.

**Access:** downloadable data files through the IPEDS data tools.

**Recommended ApplyAI use:** import institutional identities/types/locations, then discover each institution's official employment site and ATS.

## U.S. nonprofits and foundations — IRS EO BMF / TEOS bulk data

**Owner:** Internal Revenue Service

**Useful inputs:** Exempt Organizations Business Master File extract, TEOS bulk downloads and Form 990-series public datasets.

**Why useful:** large authoritative universe of U.S. tax-exempt organizations, including EIN, organization name and geographic fields.

**Access:** public bulk downloads; EO BMF is available in CSV by state/region.

**Recommended ApplyAI use:** discover major nonprofits/foundations by organization identity and location. Do not assume every tax-exempt entity is an employer or has a career site; prioritize by size/activity signals from public filings where appropriate.

## U.S. hospitals — CMS Provider Data Catalog

**Owner:** Centers for Medicare & Medicaid Services

**Useful input:** Hospital General Information dataset/API.

**Why useful:** public list of hospitals registered with Medicare with organization names and location/contact metadata.

**Access:** public CSV and Open Data API.

**Recommended ApplyAI use:** seed hospital organizations, normalize health-system aliases where evidence exists, then discover the official health-system/employer career source.

## U.S. government organizations — Data.gov / official agency directories

**Owner:** U.S. General Services Administration and publishing agencies

**Useful inputs:** federal agency/bureau directories and public government datasets.

**Why useful:** canonical agency identities for organization discovery.

**Recommended ApplyAI use:** map government organizations to official employment systems, preferring USAJOBS for federal opportunities and official state/local career systems for non-federal roles.

## Research institutions and national laboratories

Prefer authoritative agency/institution directories (for example, Department of Energy laboratory directories and university/research-system directories) over commercial lists. Import organization identities only where the publication terms permit reuse, then discover the official careers source.

## Startup universe

There is no single authoritative public government dataset equivalent to IPEDS/SEC/IRS for all startups. Treat public accelerator/VC portfolio directories as organization-discovery inputs only when their access/reuse terms permit it. The job source should normally be the startup's own Greenhouse/Lever/Ashby/other ATS or careers page.

Do not commit copied proprietary rankings or paid commercial startup datasets into the repository.

## Commercial rankings / 'Top 50,000' lists

Fortune, Forbes, Inc., proprietary market-index constituent files and commercial business databases may be useful inputs only when licensing/reuse terms allow the intended use. ApplyAI's organization importer intentionally accepts CSV/JSON/JSONL so licensed datasets can be loaded operationally without embedding proprietary data into source control.

## Ingestion policy

For every dataset loaded into the organization universe, record at least:

```text
dataset_name
dataset_owner
source_url_or_identifier
retrieved_at
license_or_public_access_note
organization_type
```

Organization datasets provide **discovery candidates**, not job-posting authority.

The preferred job authority remains:

```text
ApplyAI first-party employer
> employer official API / ATS
> employer JSON-LD / career page
> official government source
> authorized/licensed aggregator feed
> candidate import / unverified source
```

Do not infer that a dataset's public availability grants permission to crawl every linked site. Employer-page fetching remains subject to the source-policy, robots, rate-limit and safe-fetch controls implemented in ApplyAI.
