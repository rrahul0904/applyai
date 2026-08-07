import { defineConfig, devices } from "@playwright/test";

const childEnv = Object.fromEntries(
  Object.entries(process.env).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
);
const devAuthSecret = process.env.DEV_AUTH_SECRET ?? "applyai-local-development-secret-2026";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 150_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium-cleanroom", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "cd ../../services/api && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/ready",
      reuseExistingServer: false,
      timeout: 120_000,
      env: childEnv,
    },
    {
      command: "pnpm dev --hostname 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000/dev-login",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...childEnv,
        APP_ENV: "test",
        DEV_AUTH_ENABLED: "true",
        DEV_AUTH_SECRET: devAuthSecret,
        APPLYAI_API_URL: "http://127.0.0.1:8000",
        APPLYAI_OPERATOR_EMAILS: "e2e.candidate@example.test",
      },
    },
  ],
});
