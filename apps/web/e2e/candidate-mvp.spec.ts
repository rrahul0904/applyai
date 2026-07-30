import { expect, test, type Page } from "@playwright/test";

const candidateA = "e2e.candidate@example.test";
const candidateB = "e2e.other@example.test";
const persistenceNote = "E2E persistence note for the candidate application.";

async function signIn(page: Page, email: string) {
  await page.goto("/dev-login");
  await page.getByLabel("Test candidate email").fill(email);
  await page.getByRole("button", { name: "Sign in to development" }).click();
  await page.waitForURL(/\/(onboarding|dashboard)$/);
}

test("candidate MVP persists resume, profile, saved job, application, status, and note", async ({ page }) => {
  const resumePath = process.env.E2E_RESUME_PATH;
  if (!resumePath) throw new Error("E2E_RESUME_PATH is required");

  await signIn(page, candidateA);
  await expect(page).toHaveURL(/\/onboarding$/);

  await page.getByRole("button", { name: "Start setup" }).click();
  await expect(page.getByRole("heading", { name: /Start from your resume/i })).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles(resumePath);
  await expect(page.getByText("Resume processing", { exact: true })).toBeVisible();
  const reviewExtracted = page.getByRole("button", { name: "Review extracted profile" });
  await expect(reviewExtracted).toBeVisible({ timeout: 30_000 });
  await reviewExtracted.click();

  await expect(page.getByRole("heading", { name: /Review what employers should know/i })).toBeVisible();
  await expect(page.locator("#current-title")).toHaveValue("Senior Data Engineer");
  await page.locator("#headline").fill("Verified E2E data engineer");
  await page.locator("#years").fill("5");
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page.getByRole("heading", { name: "What roles are you pursuing?" })).toBeVisible();
  await page.getByLabel("Target role").fill("Data Analyst");
  await page.getByRole("button", { name: "Add role" }).click();
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page.getByRole("heading", { name: "Where do you want to work?" })).toBeVisible();
  await page.locator("#preferred-location").fill("Boston, MA");
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page.getByRole("heading", { name: "Choose the arrangements that work for you." })).toBeVisible();
  await page.getByLabel("Remote").check();
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page.getByRole("heading", { name: "Set an optional minimum salary." })).toBeVisible();
  await page.locator("#minimum-comp").fill("100000");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "Your candidate workspace is ready." })).toBeVisible();
  await page.getByRole("button", { name: /Complete onboarding/i }).click();
  await page.waitForURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Make your next move count." })).toBeVisible();

  await page.goto("/jobs");
  await page.getByLabel("Search jobs").fill("Data Analyst");
  const dataAnalystLink = page.getByRole("link", { name: "Data Analyst", exact: true }).first();
  await expect(dataAnalystLink).toBeVisible({ timeout: 15_000 });
  const jobPath = await dataAnalystLink.getAttribute("href");
  expect(jobPath).toMatch(/^\/jobs\/[0-9a-f-]+$/i);
  await dataAnalystLink.click();
  await page.waitForURL((url) => url.pathname === jobPath);
  await expect(page.getByRole("heading", { name: "Data Analyst" })).toBeVisible();

  await page.getByRole("button", { name: "Save job" }).click();
  await expect(page.getByRole("button", { name: "Saved" })).toBeVisible();
  await page.getByRole("button", { name: "Track application" }).click();
  await page.waitForURL(/\/applications\/[0-9a-f-]+$/i);
  const applicationPath = new URL(page.url()).pathname;

  await page.locator("#application-status").selectOption("APPLIED");
  await expect(page.getByText("Applied", { exact: true }).first()).toBeVisible();
  await page.locator("#application-note").fill(persistenceNote);
  await page.getByRole("button", { name: "Add note" }).click();
  await expect(page.getByText(persistenceNote)).toBeVisible();

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
  await expect(page.getByRole("link", { name: "Data Analyst", exact: true }).first()).toBeVisible();
});
