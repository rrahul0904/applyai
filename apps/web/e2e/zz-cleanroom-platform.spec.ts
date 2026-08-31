import { expect, test, type Page } from "@playwright/test";

const candidate = "e2e.candidate@example.test";

async function signIn(page: Page) {
  await page.goto("/dev-login");
  await page.getByLabel("Test candidate email").fill(candidate);
  await page.getByRole("button", { name: "Sign in to development" }).click();
  // The development sign-in action intentionally lands on /onboarding first for every
  // identity. Candidate A was fully onboarded by the canonical MVP journey earlier in this
  // same clean-room database, so navigating to the real workspace must now succeed.
  await page.waitForURL(/\/(onboarding|dashboard)$/);
  await page.goto("/dashboard");
  await page.waitForURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Your career workspace is ready." }),
  ).toBeVisible();
}

async function assertHealthy(page: Page, path: string) {
  const response = await page.goto(path, { waitUntil: "domcontentloaded" });
  expect(response, `No navigation response for ${path}`).not.toBeNull();
  expect(response!.status(), `${path} returned ${response!.status()}`).toBeLessThan(500);
  expect(new URL(page.url()).pathname, `${path} redirected away from the requested surface`).toBe(path);
  await expect(page.locator("body")).not.toContainText("Something went wrong. Please try again.");
}

test("clean-room mode renders all canonical candidate, employer, operator and public surfaces", async ({ page }) => {
  test.skip(process.env.LOCAL_CLEANROOM !== "1", "Runs only in the production-shaped local clean-room gate");

  await signIn(page);

  const candidateRoutes = [
    "/dashboard",
    "/jobs",
    "/matches",
    "/saved",
    "/applications",
    "/resume",
    "/resume/studio",
    "/career",
    "/network",
    "/analytics",
    "/alerts",
    "/billing",
    "/profile",
    "/settings",
    "/import-job",
  ];
  for (const path of candidateRoutes) await assertHealthy(page, path);

  await page.goto("/jobs");
  const jobHref = await page.locator('a[href^="/jobs/"]').first().getAttribute("href");
  expect(jobHref).toMatch(/^\/jobs\/[0-9a-f-]+$/i);
  await assertHealthy(page, jobHref!);
  const jobId = jobHref!.split("/").at(-1)!;
  await assertHealthy(page, `/interview/${jobId}`);

  await page.goto("/applications");
  const applicationHref = await page.locator('a[href^="/applications/"]').first().getAttribute("href");
  expect(applicationHref).toMatch(/^\/applications\/[0-9a-f-]+$/i);
  await assertHealthy(page, applicationHref!);

  await assertHealthy(page, "/employer");
  await assertHealthy(page, "/admin");
  await expect(page.getByRole("heading", { name: "ApplyAI Operations" })).toBeVisible();

  await assertHealthy(page, "/pricing");
  await assertHealthy(page, "/");

  await page.goto("/demo");
  await page.waitForURL(/\/dashboard$/);
  await page.goto("/beta");
  await page.waitForURL(/\/matches$/);
});
