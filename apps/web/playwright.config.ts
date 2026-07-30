import { defineConfig, devices } from "@playwright/test";

const databaseUrl =
  process.env.E2E_DATABASE_URL
  ?? "postgresql+psycopg://applyai:applyai@127.0.0.1:55432/applyai_test";
const devAuthSecret = process.env.E2E_DEV_AUTH_SECRET ?? "applyai-e2e-dev-secret";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command:
        "cd ../../services/api && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        ENVIRONMENT: "test",
        DATABASE_URL: databaseUrl,
        AUTH_PROVIDER: "dev-test",
        DEV_AUTH_ENABLED: "true",
        DEV_AUTH_SECRET: devAuthSecret,
        OBJECT_STORAGE_PROVIDER: "local",
        LOCAL_STORAGE_PATH: process.env.E2E_STORAGE_PATH ?? "/tmp/applyai-e2e-resumes",
        TASK_QUEUE_PROVIDER: "memory",
        WEB_ORIGIN: "http://127.0.0.1:3000",
      },
    },
    {
      command: "pnpm dev --hostname 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000/dev-login",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        APP_ENV: "test",
        DEV_AUTH_ENABLED: "true",
        DEV_AUTH_SECRET: devAuthSecret,
        APPLYAI_API_URL: "http://127.0.0.1:8000",
      },
    },
  ],
});
