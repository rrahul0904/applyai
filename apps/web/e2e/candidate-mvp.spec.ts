import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

const candidateA = "e2e.candidate@example.test";
const candidateB = "e2e.other@example.test";
const persistenceNote = "E2E persistence note for the candidate application.";
const demoCaptureDir = process.env.DEMO_CAPTURE_DIR;

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
  });
}

test("candidate MVP persists resume, profile, saved job, application, status, and note", async ({ page }) => {
  const resumePath = process.env.E2E_RESUME_PATH;
  if (!resumePath) throw new Error("E2E_RESUME_PATH is required");

  await signIn(page, candidateA);
  await expect(page).toHaveURL(/\/onboarding$/);

  await page.getByRole("button", { name: "Start setup" }).click();
  await expect(page.getByRole("heading", { name: /Start from your resume/i })).toBeVisible();
  await captureDemo(page, "01-onboarding-resume");

  await page.locator('input[type="file"]').setInputFiles(resumePath);
  await expect(page.getByText("Resume processing", { exact: true })).toBeVisible();
  const reviewExtracted = page.getByRole("button", { name: "Review extracted profile" });
  await expect(reviewExtracted).toBeVisible({ timeout: 30_000 });
  await reviewExtracted.click();

  await expect(page.getByRole("heading", { name: /Review what employers should know/i })).toBeVisible();
  await expect(page.locator("#current-title")).toHaveValue("Senior Data Engineer");
  await page.locator("#headline").fill("Verified E2E data engineer");
  await page.locator("#years").fill("5");
  await captureDemo(page, "02-profile-review");
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page.getByRole("heading", { name: "What roles are you pursuing?" })).toBeVisible();
  await page.getByLabel("Target role").fill("Data Analyst");
  await page.getByRole("button", { name: "Add role" }).click();
  await captureDemo(page, "03-target-roles");
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page.getByRole("heading", { name: "Where do you want to work?" })).toBeVisible();
  await page.locator("#preferred-location").fill("Boston, MA");
  await captureDemo(page, "04-location-preferences");
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page.getByRole("heading", { name: "Choose the arrangements that work for you." })).toBeVisible();
  await page.getByLabel("Remote").check();
  await captureDemo(page, "05-work-mode");
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page.getByRole("heading", { name: "Set an optional minimum salary." })).toBeVisible();
  await page.locator("#minimum-comp").fill("100000");
  await captureDemo(page, "06-compensation");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "Your candidate workspace is ready." })).toBeVisible();
  await captureDemo(page, "07-onboarding-complete");
  await page.getByRole("button", { name: /Complete onboarding/i }).click();
  await page.waitForURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Your career workspace is ready." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Opportunities worth inspecting" })).toBeVisible();
  await captureDemo(page, "08-dashboard");

  await page.goto("/jobs");
  await page.getByLabel("Search jobs").fill("Data Analyst");
  await page.waitForURL(
    (url) => url.pathname === "/jobs" && url.searchParams.get("keyword") === "Data Analyst",
  );
  const dataAnalystCard = page
    .locator(".job-card")
    .filter({ has: page.getByRole("heading", { name: "Data Analyst", exact: true }) })
    .first();
  await expect(dataAnalystCard).toBeVisible({ timeout: 15_000 });
  await captureDemo(page, "09-job-search");
  const detailLink = dataAnalystCard.getByRole("link", { name: "Review role" });
  const jobPath = await detailLink.getAttribute("href");
  expect(jobPath).toMatch(/^\/jobs\/[0-9a-f-]+$/i);
  await detailLink.click();
  await page.waitForURL((url) => url.pathname === jobPath);
  await expect(page.getByRole("heading", { name: "Data Analyst" })).toBeVisible();
  await captureDemo(page, "10-job-detail");

  await page.getByRole("button", { name: "Save for later" }).click();
  await expect(page.getByRole("button", { name: "Saved for later" })).toBeVisible();
  await page.getByRole("button", { name: "Start application", exact: true }).click();
  await page.waitForURL(/\/applications\/[0-9a-f-]+$/i);
  const applicationPath = new URL(page.url()).pathname;

  await page.locator("#application-status").selectOption("APPLIED");
  await expect(page.getByText("Applied", { exact: true }).first()).toBeVisible();
  await page.locator("#application-note").fill(persistenceNote);
  await page.getByRole("button", { name: "Save note" }).click();
  await expect(page.getByText(persistenceNote)).toBeVisible();
  await captureDemo(page, "11-application-workspace");

  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL("/");

  await signIn(page, candidateB);
  const isolatedApplication = await page.request.get(`/api/backend${applicationPath}`);
  expect(isolatedApplication.status()).toBe(404);
  const isolatedSaved = await page.request.get("/api/backend/jobs/saved");
  expect(isolatedSaved.status()).toBe(200);
  expect((await isolatedSaved.json()).items).toEqual([]);

  // Candidate B is still in onboarding and intentionally has no candidate-shell
  // sign-out control. Clearing the controlled dev cookie switches test identity;
  // production/staging E2E uses Clerk and must verify its real sign-out flow.
  await page.context().clearCookies();

  await signIn(page, candidateA);
  await page.waitForURL(/\/dashboard$/);
  await page.goto(applicationPath);
  await expect(page.locator("#application-status")).toHaveValue("APPLIED");
  await expect(page.getByText(persistenceNote)).toBeVisible();

  await page.goto("/saved");
  await expect(
    page
      .locator(".job-card")
      .filter({ has: page.getByRole("heading", { name: "Data Analyst", exact: true }) })
      .first(),
  ).toBeVisible();
  await captureDemo(page, "12-saved-jobs");
});
