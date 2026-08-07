# Mobile and Browser Extension

## Native mobile

The native candidate client is under `/mobile` and intentionally remains outside the pnpm web workspace so its Expo dependency graph can evolve independently of Next.js. It uses the same authenticated FastAPI APIs as the web product and does not introduce a second backend.

Implemented mobile surfaces: AI Matches, Jobs, Applications, Alerts and Profile/Career Memory summary. Clerk hosted auth + secure token cache protect mobile sessions.

## Browser extension

The Manifest V3 extension is under `/apps/extension`. It has only `activeTab` and `storage` permissions. After a user click it sends the current public URL to the authenticated `/import-job` web workspace. Server-side URL validation, robots policy, redirect checks, response-size budgets and structured extraction remain authoritative.

No extension code scrapes private pages, bypasses authentication, solves CAPTCHAs or submits employer forms.

## External distribution boundary

The following are deployment/distribution work rather than missing source:

- Apple/Google developer accounts and signing credentials
- EAS/native release builds
- App Store / Play Store review and publication
- Chrome/Edge extension store signing and publication
