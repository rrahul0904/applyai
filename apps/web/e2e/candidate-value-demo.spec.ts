import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

const demoCaptureDir = process.env.DEMO_CAPTURE_DIR;
const candidate = "e2e.candidate@example.test";

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

test("canonical candidate product persists cross-workspace career state", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signIn(page, candidate);

  await page.goto("/demo");
  await page.waitForURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Make your next move count." })).toBeVisible();
  await captureDemo(page, "13-canonical-workspace-overview");

  await page.goto("/applications");
  await expect(page.getByRole("heading", { name: /applications/i }).first()).toBeVisible();
  await expect(page.getByText("E2E persistence note for the candidate application.")).toBeVisible();
  await captureDemo(page, "14-application-command-center");

  await page.goto("/resume/studio");
  await expect(page.getByRole("heading", { name: "Resume Studio" })).toBeVisible();
  await page.getByRole("button", { name: "New variant" }).click();
  await page.getByLabel("Professional summary").fill("Verified E2E data engineer focused on reliable data platforms.");
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(page.getByText(/Version 2/)).toBeVisible();
  await page.reload();
  await expect(page.getByDisplayValue("Verified E2E data engineer focused on reliable data platforms.")).toBeVisible();
  await captureDemo(page, "15-resume-studio-persistence");

  await page.goto("/network");
  await page.getByLabel("Name").fill("E2E Hiring Manager");
  await page.getByLabel("Company").fill("ApplyAI Demo Employer");
  await page.getByRole("button", { name: "Add contact" }).click();
  await expect(page.getByText("E2E Hiring Manager")).toBeVisible();
  await page.reload();
  await expect(page.getByText("E2E Hiring Manager")).toBeVisible();

  await page.goto("/analytics");
  await expect(page.getByRole("heading", { name: "Candidate Analytics" })).toBeVisible();
  await expect(page.getByText("Resume variants")).toBeVisible();
  await expect(page.getByText("Network contacts")).toBeVisible();
  await captureDemo(page, "16-candidate-analytics");
});
