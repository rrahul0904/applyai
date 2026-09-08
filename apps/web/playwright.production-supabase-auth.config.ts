import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.APPLYAI_PRODUCTION_URL ?? "https://applyai-gold.vercel.app";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /production-supabase-auth\.spec\.ts/,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["line"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "production-supabase-auth-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
