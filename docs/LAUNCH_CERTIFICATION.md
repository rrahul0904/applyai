# ApplyAI Launch Certification

ApplyAI is launch-ready only when every required gate below has evidence for the same release candidate SHA. A green repository build by itself is not a production-readiness claim.

## Automated repository gates

- ApplyAI CI: lint, typecheck, web tests, API tests, migration drift, container builds, Terraform validation, Candidate MVP Playwright.
- Full Functional Certification and Local Clean-room Certification.
- Launch Security: focused security regressions, Bandit SAST, Python dependency audit, pnpm production dependency audit, and high-confidence committed-secret scanning.
- Existing agent runtime, job-search, job-supply, provider, auth, Supabase policy, and workflow validation gates.

## Hosted staging gates

- Deploy the exact release candidate SHA to staging.
- Run Staging Verification V2 and retain the workflow artifact.
- Confirm API health/readiness, target health, runtime image consistency, private networking, queue/worker availability, and the essential SQS-backed Radar scheduler sidecar.
- Run `ApplyAI Authorized Staging DAST` in `baseline` mode first. Resolve or explicitly risk-accept findings before running `full` active mode.
- Run `ApplyAI Authorized Staging Performance Smoke` against the exact candidate deployment; require zero failed public-surface requests and p95 <= 2500 ms under its bounded five-worker smoke.
- Run the `full` DAST scan only against the allow-listed ApplyAI-owned staging/preview deployment. Never point it at third-party job boards or external applicant-tracking systems.

## Candidate acceptance / user testing

Automated Playwright is necessary but is not a substitute for human usability testing. Before launch, record at least five representative candidate sessions covering:

1. Sign up/sign in and onboarding.
2. Profile and resume creation/import.
3. Job discovery, filtering, match detail, save and application tracking.
4. Application-agent approval boundaries and human-required handoffs.
5. Radar alerts and saved searches.
6. Interview preparation, coding submission history, discussion and coaching.
7. Settings, privacy controls, data export/deletion entry points and sign-out.
8. Mobile-width and keyboard-only navigation.

For each session capture release SHA, browser/device, pass/fail by journey, confusing copy or navigation, accessibility observations, severity, and follow-up issue links. P0/P1 usability or safety defects block launch.

## Security acceptance

- No unresolved critical/high dependency vulnerabilities in production dependencies.
- No unresolved high-confidence Bandit findings without a documented false-positive or risk acceptance.
- No committed production credentials or private keys.
- Authorization regression tests cover candidate ownership and internal/operator boundaries.
- Upload/parser security tests remain green.
- ZAP staging evidence has no unresolved high-risk finding; medium findings require explicit disposition before launch.
- Rate limiting, CORS, auth/session behavior, secrets storage, database/storage encryption and backup/restore are verified in the hosted environment.

## Operational acceptance

- Exact release SHA is identifiable in web/API/worker deployments.
- Rollback workflow is exercised against staging.
- Logs, error reporting and alerting are observable for web, API, queues and workers.
- Backup/restore and data-deletion runbooks have been exercised.
- A release owner records GO/NO-GO only after repository, staging, security, UAT and operational evidence all refer to the same candidate SHA.

## Evidence boundary

Repository workflows certify repository behavior. Vercel preview readiness certifies only that the web deployment built and became reachable. AWS/Vercel hosted runtime, penetration/DAST, real-user acceptance, backup/restore and operational observability require separate evidence and must not be inferred from CI.