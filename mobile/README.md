# ApplyAI Native Mobile

ApplyAI's candidate mobile client uses Expo SDK 57 / React Native 0.86 and the current `@clerk/expo` package. It consumes the same authenticated FastAPI contract as the web product.

Implemented native screens:

- AI Matches
- job search
- application tracking
- alerts and reminders
- candidate profile / Career Memory summary

Authentication uses Clerk's hosted auth flow and secure token cache. API calls attach the current Clerk bearer token and never embed backend credentials.

## Run locally

```bash
cd mobile
cp .env.example .env
npm install
npx expo start
```

Required configuration:

```text
EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY
EXPO_PUBLIC_API_BASE_URL
```

Native signing certificates, Apple/Google developer accounts, EAS/App Store builds and store publication are deployment/distribution activities and are intentionally not stored in source control.
