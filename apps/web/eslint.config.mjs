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
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);
