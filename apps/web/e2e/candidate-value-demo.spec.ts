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
  await expect(page.getByRole("heading", { name: "Your career workspace is ready." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Opportunities worth inspecting" })).toBeVisible();
  await captureDemo(page, "13-candidate-home");

  await page.goto("/applications");
  await expect(page.getByRole("heading", { name: "Keep every opportunity moving." })).toBeVisible();
  const firstApplication = page.locator("a.application-row").first();
  await expect(firstApplication).toBeVisible();
  await firstApplication.click();
  await expect(page.getByText("E2E persistence note for the candidate application.")).toBeVisible();
  await captureDemo(page, "14-application-workspace");

  await page.goto("/resume/studio");
  await expect(page.getByRole("heading", { name: "A strong resume, grounded in what you've actually done." })).toBeVisible();
  await page.getByRole("button", { name: "New resume" }).click();
  await page.getByLabel("Professional summary").fill("Verified E2E data engineer focused on reliable data platforms.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.reload();
  await expect(page.getByLabel("Professional summary")).toHaveValue("Verified E2E data engineer focused on reliable data platforms.");
  await captureDemo(page, "15-resume-workspace-persistence");

  await page.goto("/network");
  await page.getByLabel("Name").fill("E2E Hiring Manager");
  await page.getByLabel("Company").fill("ApplyAI Demo Employer");
  await page.getByRole("button", { name: "Add contact" }).click();
  await expect(page.getByText("E2E Hiring Manager")).toBeVisible();
  await page.reload();
  await expect(page.getByText("E2E Hiring Manager")).toBeVisible();

  await page.goto("/analytics");
  await expect(page.getByRole("heading", { name: "See where your search is moving." })).toBeVisible();
  await expect(page.getByText("Resume versions")).toBeVisible();
  await expect(page.getByText("Network contacts")).toBeVisible();
  await captureDemo(page, "16-candidate-progress");
});
