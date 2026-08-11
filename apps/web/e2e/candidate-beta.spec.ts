import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

const demoCaptureDir = process.env.DEMO_CAPTURE_DIR;
const candidate = "e2e.platform@example.test";

async function signIn(page: Page, email: string) {
  await page.goto("/dev-login");
  await page.getByLabel("Test candidate email").fill(email);
  await page.getByRole("button", { name: "Sign in to development" }).click();
  await page.waitForURL(/\/(onboarding|dashboard)$/);
}

async function captureDemo(page: Page, fileName: string) {
  if (!demoCaptureDir) return;
  mkdirSync(demoCaptureDir, { recursive: true });
  await page.screenshot({
    path: join(demoCaptureDir, `${fileName}.png`),
    fullPage: true,
    animations: "disabled",
  });
}

test("retired beta entry resolves into the canonical candidate platform", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signIn(page, candidate);

  await page.goto("/beta");
  await page.waitForURL(/\/matches$/);
  await expect(page.getByRole("heading", { name: "Start with the roles that fit best." })).toBeVisible();
  await expect(page.getByText(/combine your goals, preferences, and verified experience/i)).toBeVisible();
  await captureDemo(page, "17-recommended-jobs");

  await page.goto("/resume/studio");
  await expect(page.getByRole("heading", { name: "A strong resume, grounded in what you've actually done." })).toBeVisible();
  await page.getByRole("button", { name: "New resume" }).click();
  await expect(page.getByRole("heading", { name: "New resume" })).toBeVisible();
  await page.getByLabel("Professional summary").fill("Evidence-backed platform leadership summary.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByLabel("Professional summary")).toHaveValue("Evidence-backed platform leadership summary.");
  await captureDemo(page, "18-resume-workspace");

  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Let the right opportunities come to you." })).toBeVisible();
  await page.getByLabel("Alert name").fill("Data platform leadership");
  await page.getByLabel("Keyword").fill("Data");
  await page.getByRole("button", { name: "Create alert" }).click();
  await expect(page.getByText("Data platform leadership")).toBeVisible();
  await captureDemo(page, "19-alerts-and-followups");

  await page.goto("/network");
  await expect(page.getByRole("heading", { name: "Network" })).toBeVisible();
  await page.getByLabel("Name").fill("Recruiter Example");
  await page.getByLabel("Company").fill("ApplyAI Example");
  await page.getByLabel("Email").fill("recruiter@example.test");
  await page.getByRole("button", { name: "Add contact" }).click();
  await expect(page.getByText("Recruiter Example")).toBeVisible();
  await captureDemo(page, "20-network-workspace");
});
