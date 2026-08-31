# ApplyAI Cloudflare R2 Storage

Updated: 2026-08-31

## Role

Cloudflare R2 is the private résumé/document object store for the ApplyAI lean production profile. The application continues using the existing S3-compatible storage abstraction so AWS S3 remains supported by the optional AWS scale profile.

Production bucket:

```text
applyai-resumes
```

Do not reuse a bucket belonging to another application.

## Required server-side configuration

```text
OBJECT_STORAGE_PROVIDER=s3
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_BUCKET=applyai-resumes
S3_REGION=auto
S3_ACCESS_KEY_ID=<secret>
S3_SECRET_ACCESS_KEY=<secret>
S3_SERVER_SIDE_ENCRYPTION=none
```

R2 credentials are server-side secrets. They must never appear in `NEXT_PUBLIC_*`, browser bundles, logs, public résumé payloads, or source control.

## Provider compatibility

The same storage adapter supports AWS S3. AWS can continue using:

```text
S3_SERVER_SIDE_ENCRYPTION=AES256
```

R2 mode intentionally omits the AWS `x-amz-server-side-encryption: AES256` PutObject header. Direct-upload response headers are owned by the storage provider rather than hardcoded in the résumé API.

## Security requirements

The production bucket must remain private:

- no public bucket listing;
- no public read policy for résumé objects;
- no permanent raw object URLs;
- short-lived signed PUT/GET URLs only where the application uses direct transfers;
- API-enforced candidate ownership;
- MIME and size validation retained;
- parser hardening retained;
- deletion of candidate-owned résumé data removes the underlying private object when the product deletion flow requires it.

Resume Share Intelligence is a controlled public application route. It must not expose the R2 object key, R2 credentials, or a permanent private-object URL.

## Live acceptance

The repository includes:

```text
services/api/scripts/r2_acceptance.py
.github/workflows/r2-live-acceptance.yml
```

Required GitHub/provider secrets:

```text
APPLYAI_R2_ENDPOINT_URL
APPLYAI_R2_BUCKET
APPLYAI_R2_ACCESS_KEY_ID
APPLYAI_R2_SECRET_ACCESS_KEY
```

The live acceptance performs a bounded disposable-object flow:

```text
PUT
HEAD
GET
content verification
presigned PUT
DELETE
```

The temporary acceptance object must be deleted when the run completes.

Do not classify R2 as `LIVE_PREVIEW_VERIFIED` or `LIVE_PRODUCTION_VERIFIED` until this real-provider acceptance passes.

## Candidate résumé acceptance

After R2 provider acceptance, verify with a synthetic résumé:

```text
candidate upload
→ private R2 object
→ upload completion verification
→ TaskOutbox
→ postgres_tasks
→ Railway résumé processor
→ candidate review
```

Test PDF and DOCX plus invalid/oversized/encrypted/adversarial document handling. No parser result becomes verified candidate truth without candidate review.

## Current external gate

No authorized Cloudflare/R2 connection or production R2 credentials are exposed to the current implementation session. Source support and live acceptance tooling are present, but a bucket or credential cannot be truthfully reported as created until the account owner supplies provider authorization.
