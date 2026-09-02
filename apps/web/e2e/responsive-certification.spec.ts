import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

const candidate = "e2e.candidate@example.test";
const captureDir = process.env.DEMO_CAPTURE_DIR;

const viewports = [
  { name: "mobile-375", width: 375, height: 812 },
  { name: "mobile-390", width: 390, height: 844 },
  { name: "mobile-430", width: 430, height: 932 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "tablet-820", width: 820, height: 1180 },
  { name: "tablet-1024-landscape", width: 1024, height: 768 },
  { name: "laptop-1280", width: 1280, height: 800 },
  { name: "desktop-1440", width: 1440, height: 900 },
] as const;

async function signIn(page: Page) {
  await page.goto("/dev-login");
  await page.getByLabel("Test candidate email").fill(candidate);
  await page.getByRole("button", { name: "Sign in to development" }).click();
  await page.waitForURL(/\/(onboarding|dashboard)$/);
  await page.goto("/demo");
  await page.waitForURL(/\/dashboard$/);
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 1);
}

async function capture(page: Page, name: string) {
  if (!captureDir) return;
  mkdirSync(captureDir, { recursive: true });
  await page.screenshot({
    path: join(captureDir, `${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
}

async function expectPrimaryNavigation(page: Page, width: number) {
  const mobileNav = page.locator(".cx-mobile-nav");
  const sidebar = page.locator(".cx-sidebar");
  if (width <= 900) {
    await expect(mobileNav).toBeVisible();
    await expect(sidebar).toBeHidden();
    const homeTarget = mobileNav.getByRole("link", { name: "Home" });
    const box = await homeTarget.boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  } else {
    await expect(sidebar).toBeVisible();
    await expect(mobileNav).toBeHidden();
  }
}

test("Career Command OS is responsive across certified mobile, tablet, and desktop breakpoints", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page);

  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Your career workspace is ready." })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Opportunities worth inspecting" })).toBeVisible();
    await expectPrimaryNavigation(page, viewport.width);
    await expectNoHorizontalOverflow(page);
    await capture(page, `responsive-${viewport.name}-home`);

    await page.goto("/jobs");
    await expect(page.getByLabel("Search jobs")).toBeVisible();
    await expect(page.locator(".job-card").first()).toBeVisible();
    await expectNoHorizontalOverflow(page);

    if (viewport.width <= 900) {
      const filterButton = page.getByRole("button", { name: /Filter/i });
      await expect(filterButton).toBeVisible();
      const filterBox = await filterButton.boundingBox();
      expect(filterBox?.height ?? 0).toBeGreaterThanOrEqual(44);
    }

    const saveButton = page.locator(".job-card").first().getByRole("button", { name: /Save job|Remove from saved jobs/i });
    const saveBox = await saveButton.boundingBox();
    expect(saveBox?.height ?? 0).toBeGreaterThanOrEqual(44);
    expect(saveBox?.width ?? 0).toBeGreaterThanOrEqual(44);
    await capture(page, `responsive-${viewport.name}-jobs`);

    await page.goto("/applications");
    await expect(page.getByRole("heading", { name: "Keep every opportunity moving." })).toBeVisible();
    await expect(page.locator("a.application-row").first()).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await capture(page, `responsive-${viewport.name}-applications`);
  }
});

test("mobile job detail keeps decisions and Recruiter Lens readable without overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);
  await page.goto("/jobs");

  const firstCard = page.locator(".job-card").first();
  await expect(firstCard).toBeVisible();
  await firstCard.getByRole("link", { name: "Review role" }).click();
  await page.waitForURL(/\/jobs\/[0-9a-f-]+$/i);

  await expect(page.getByRole("heading", { name: "Should you pursue this?" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recruiter Lens" })).toBeVisible();
  await expect(page.getByText(/not an employer decision/i)).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const startApplication = page.getByRole("button", { name: "Start application" });
  const actionBox = await startApplication.boundingBox();
  expect(actionBox?.height ?? 0).toBeGreaterThanOrEqual(44);

  const perspectiveSelect = page.getByLabel("Perspective");
  await expect(perspectiveSelect).toBeVisible();
  await capture(page, "responsive-mobile-390-job-detail-recruiter-lens");
});
