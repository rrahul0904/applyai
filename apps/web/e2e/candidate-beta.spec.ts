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
  await expect(page.getByRole("heading", { name: "AI Matches" })).toBeVisible();
  await expect(page.getByText(/Scores prioritize your search/i)).toBeVisible();
  await captureDemo(page, "17-ai-match-prioritization");

  await page.goto("/resume/studio");
  await expect(page.getByRole("heading", { name: "Resume Studio" })).toBeVisible();
  await page.getByRole("button", { name: "New variant" }).click();
  await expect(page.getByRole("heading", { name: "New resume variant" })).toBeVisible();
  await page.getByLabel("Professional summary").fill("Evidence-backed platform leadership summary.");
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(page.getByText(/Version 2/)).toBeVisible();
  await captureDemo(page, "18-evidence-locked-resume-studio");

  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts & Follow-ups" })).toBeVisible();
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
