import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["components/onboarding-view.tsx"],
    rules: {
      // Onboarding intentionally hydrates a local, user-editable draft from async
      // profile/parser results. The effects are guarded and must run only when
      // those external query results become available.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  {
    files: ["app/demo/functional-candidate-demo.tsx"],
    rules: {
      // The functional demo bootstraps a controlled session and then hydrates from
      // several authenticated APIs. State changes occur after those external calls.
      "react-hooks/set-state-in-effect": "off",
      // The unauthenticated fallback must remain a plain navigation target because
      // the demo route can run without the Clerk provider mounted.
      "@next/next/no-html-link-for-pages": "off",
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);
