# ApplyAI full-functional certification

This document defines the no-deploy certification boundary for ApplyAI.

## Scope

The certification proves repository-controlled behavior without creating a Vercel deployment.

Vercel deployment is intentionally excluded from this phase.

The certification is split into three evidence classes:

1. **Repository functional contract** — required Operations/API/UI/test surfaces exist.
2. **Clean-room runtime certification** — PostgreSQL, LocalStack S3/SQS, workers, FastAPI, Next.js, provider mocks, migrations, API/web/OpenAPI checks and browser journeys execute from a fresh environment.
3. **Production real-inventory gate** — at least 2,000,000 legitimate real canonical jobs are present. Synthetic, demo, development, fixture, seed, benchmark, test and generated rows must never satisfy this gate.

## Commands

### Start the complete local website

```bash
pnpm dev:full
```

This starts the local infrastructure and application runtime:

- PostgreSQL
- LocalStack S3/SQS
- Mailpit
- local provider protocol mock
- task outbox
- resume worker
- source worker
- AI worker
- agent worker
- FastAPI
- Next.js

The website is available at `http://127.0.0.1:3000`.

### Run the existing clean-room certification

```bash
pnpm test:full
```

This delegates to `scripts/local-certify.sh`.

### Verify the full-functional repository contract

```bash
pnpm release:contract
```

The verifier is fail-closed. It checks for the operational implementation required by the current phase, including the durable `SOURCE_INGEST` worker/outbox, Operations API, Operations UI, persisted certification migration, backend Operations tests, browser Operations E2E, candidate E2E, clean-room harness and screenshot workflow.

Evidence is written to:

```text
artifacts/predeploy/full-functional-contract.json
```

### Run authoritative no-deploy certification

```bash
REAL_INVENTORY_GATE_CMD='<strict production certification command>' \
pnpm release:predeploy-certify
```

The command runs the repository contract and clean-room runtime certification first.

By default it then requires a strict real-inventory command. If no production inventory command is supplied, certification exits non-zero rather than silently treating benchmark data as production readiness.

The production gate must prove:

```text
eligible_real_jobs >= 2_000_000
```

and must exclude synthetic/demo/development/test/fixture/seed/benchmark/generated inventory.

## Repository-only CI mode

GitHub Actions runs the repository-controlled gate with:

```text
REQUIRE_REAL_INVENTORY=0
```

This does **not** certify production inventory. It records that production inventory remains a separate external/runtime evidence gate while still requiring every repository-controlled check to pass.

## UI evidence

The existing demo-capture workflow captures real rendered application screens. The full-functional workflow uploads:

- contract JSON
- predeploy reports
- clean-room logs
- Playwright reports
- Playwright test results
- rendered screenshots when present

Generated design mockups are not release evidence.

## Failure semantics

A missing Operations API, Operations UI, Operations migration, required test, queue-backed ingestion capability, or clean-room runtime failure is a repository-controlled failure and must fail CI.

A production inventory count below 2M is a production-readiness failure and must never be converted to PASS through synthetic scale data.

The 2M scale benchmark and 2M real-job inventory gate are independent evidence classes.

## Deployment boundary

Every certification report must preserve this statement:

```text
Vercel deployment:
NOT PERFORMED — intentionally excluded from this implementation phase.
```
