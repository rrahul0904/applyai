import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

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

async function expectMinimumHitArea(target: Locator, minimumSize = 44) {
  await expect(target).toBeVisible();
  const box = await target.boundingBox();
  expect(box, "Expected a visible interactive control with a measurable hit area").not.toBeNull();
  if (!box) throw new Error("Interactive control did not expose a measurable hit area");
  expect(box.height).toBeGreaterThanOrEqual(minimumSize);
  expect(box.width).toBeGreaterThanOrEqual(minimumSize);
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
    await expectMinimumHitArea(homeTarget, 44);
  } else {
    await expect(sidebar).toBeVisible();
    await expect(mobileNav).toBeHidden();
  }
}

test("Career Command OS is responsive across certified mobile, tablet, and desktop breakpoints", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page);

  for (const viewport of viewports) {
    await test.step(viewport.name, async () => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });

      await page.goto("/dashboard");
      await expect(page.getByRole("heading", { name: "Your career workspace is ready." })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Opportunities worth inspecting" })).toBeVisible();
      await expectPrimaryNavigation(page, viewport.width);
      await expectNoHorizontalOverflow(page);
      await capture(page, `responsive-${viewport.name}-home`);

      await page.goto("/jobs");
      await expect(page.getByLabel("Search jobs")).toBeVisible();
      const firstCard = page.locator(".job-card").first();
      await expect(firstCard).toBeVisible();
      await expectNoHorizontalOverflow(page);

      if (viewport.width <= 900) {
        const filterButton = page.getByRole("button", { name: /Filter/i });
        await expectMinimumHitArea(filterButton, viewport.width <= 700 ? 48 : 44);
      }

      // JobCard intentionally names the bookmark action with the concrete job title,
      // e.g. "Save Senior Analyst" / "Unsave Senior Analyst". Certify that semantic
      // contract instead of relying on copy that the product does not render.
      const saveButton = firstCard.getByRole("button", { name: /^(Save|Unsave) .+/i });
      await expect(saveButton).toBeEnabled();
      await expectMinimumHitArea(saveButton, viewport.width <= 700 ? 48 : 44);
      await capture(page, `responsive-${viewport.name}-jobs`);

      await page.goto("/applications");
      await expect(page.getByRole("heading", { name: "Keep every opportunity moving." })).toBeVisible();
      await expect(page.locator("a.application-row").first()).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await capture(page, `responsive-${viewport.name}-applications`);
    });
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

  // The deliberate candidate decision heading in JobDetailView is "Pursue this opportunity?".
  // Keep certification aligned to the rendered accessible contract rather than historical copy.
  await expect(page.getByRole("heading", { name: "Pursue this opportunity?" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recruiter Lens" })).toBeVisible();
  await expect(page.getByText(/not an employer decision/i)).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const startApplication = page.getByRole("button", { name: "Start application" });
  await expect(startApplication).toBeEnabled();
  await expectMinimumHitArea(startApplication, 48);

  const perspectiveSelect = page.getByLabel("Perspective");
  await expect(perspectiveSelect).toBeVisible();
  await capture(page, "responsive-mobile-390-job-detail-recruiter-lens");
});
