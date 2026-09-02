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

const darkModeViewports = [
  { name: "mobile-390", width: 390, height: 844 },
  { name: "tablet-820", width: 820, height: 1180 },
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

test("mobile job detail keeps decisions and Recruiter Lens readable and keyboard operable", async ({ page }) => {
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

  const startApplication = page.getByRole("button", { name: "Start application", exact: true });
  await expect(startApplication).toBeEnabled();
  await expectMinimumHitArea(startApplication, 48);

  // Restrict the semantic query to the native select so the desktop perspective button group
  // cannot collide with the mobile fallback's accessible label.
  const perspectiveSelect = page.getByRole("combobox", { name: /Perspective/i });
  await expect(perspectiveSelect).toBeVisible();
  await perspectiveSelect.focus();
  await expect(perspectiveSelect).toBeFocused();

  await capture(page, "responsive-mobile-390-job-detail-recruiter-lens");

  // The button copy changes after expansion, so anchor to the stable disclosure relationship.
  const criteriaDisclosure = page.locator('button[aria-controls="recruiter-lens-criteria"]');
  await expect(criteriaDisclosure).toHaveAttribute("aria-expanded", "false");
  await criteriaDisclosure.focus();
  await expect(criteriaDisclosure).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(criteriaDisclosure).toHaveAttribute("aria-expanded", "true");

  const concernsDetails = page.locator("details").filter({ hasText: "Potential concerns" }).first();
  const concernsSummary = concernsDetails.locator("summary");
  await concernsSummary.focus();
  await expect(concernsSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(concernsDetails).toHaveAttribute("open", "");

  const questionsDetails = page.locator("details").filter({ hasText: "Questions to prepare for" }).first();
  const questionsSummary = questionsDetails.locator("summary");
  await questionsSummary.focus();
  await expect(questionsSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(questionsDetails).toHaveAttribute("open", "");
  await expectNoHorizontalOverflow(page);
});

test("long candidate content wraps safely without widening the mobile document", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);
  await page.goto("/jobs");

  const firstCard = page.locator(".job-card").first();
  await expect(firstCard).toBeVisible();
  await firstCard.locator("h2").evaluate((node) => {
    node.textContent = "Senior Principal Cross-Functional Product Strategy and Enterprise Transformation Lead for Global Platforms";
  });
  await firstCard.locator(".job-company").evaluate((node) => {
    node.textContent = "Northstar International Health Technology and Research Collaborative Incorporated";
  });
  await expectNoHorizontalOverflow(page);
  await capture(page, "responsive-mobile-390-jobs-long-content");

  await firstCard.getByRole("link", { name: "Review role" }).click();
  await page.waitForURL(/\/jobs\/[0-9a-f-]+$/i);
  const criteria = page.locator("#recruiter-lens-criteria");
  await expect(criteria).toBeVisible();
  await criteria.locator("strong").first().evaluate((node) => {
    node.textContent = "Demonstrated enterprise product strategy ownership across globally distributed multidisciplinary stakeholder groups";
  });

  const concernsDetails = page.locator("details").filter({ hasText: "Potential concerns" }).first();
  await concernsDetails.locator("summary").click();
  await concernsDetails.locator("p").first().evaluate((node) => {
    node.textContent = "The candidate should be prepared to explain how adjacent experience transfers to unusually broad cross-functional product strategy ownership without overstating verified evidence.";
  });

  const questionsDetails = page.locator("details").filter({ hasText: "Questions to prepare for" }).first();
  await questionsDetails.locator("summary").click();
  await questionsDetails.locator("p").first().evaluate((node) => {
    node.textContent = "Describe a complex cross-functional initiative where requirements, stakeholder priorities, measurement strategy, technical constraints, and delivery ownership all changed over time.";
  });
  await expectNoHorizontalOverflow(page);
  await capture(page, "responsive-mobile-390-job-detail-long-content");

  await page.goto("/applications");
  const firstApplication = page.locator("a.application-row").first();
  await expect(firstApplication).toBeVisible();
  await firstApplication.locator(".role").evaluate((node) => {
    node.textContent = "Senior Principal Cross-Functional Product Strategy and Enterprise Transformation Lead";
  });
  await firstApplication.locator(".company").evaluate((node) => {
    node.textContent = "Northstar International Health Technology and Research Collaborative Incorporated";
  });
  await firstApplication.locator(".activity").evaluate((node) => {
    node.textContent = "Updated after a detailed candidate review of application materials, follow-up context, interview preparation, and supporting verified evidence.";
  });
  await expectNoHorizontalOverflow(page);
  await capture(page, "responsive-mobile-390-applications-long-content");
});

test("dark mode with reduced motion remains usable at representative responsive breakpoints", async ({ page }) => {
  test.setTimeout(240_000);
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page);

  const mediaPreferences = await page.evaluate(() => ({
    dark: window.matchMedia("(prefers-color-scheme: dark)").matches,
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  }));
  expect(mediaPreferences).toEqual({ dark: true, reducedMotion: true });

  for (const viewport of darkModeViewports) {
    await test.step(viewport.name, async () => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/jobs");
      await expect(page.getByLabel("Search jobs")).toBeVisible();
      await expectPrimaryNavigation(page, viewport.width);

      const firstCard = page.locator(".job-card").first();
      await expect(firstCard).toBeVisible();
      const saveButton = firstCard.getByRole("button", { name: /^(Save|Unsave) .+/i });
      await expectMinimumHitArea(saveButton, viewport.width <= 700 ? 48 : 44);
      await expectNoHorizontalOverflow(page);
      await capture(page, `responsive-${viewport.name}-jobs-dark-reduced-motion`);

      if (viewport.width === 390) {
        await firstCard.getByRole("link", { name: "Review role" }).click();
        await page.waitForURL(/\/jobs\/[0-9a-f-]+$/i);
        await expect(page.getByRole("heading", { name: "Recruiter Lens" })).toBeVisible();
        await expect(page.getByText(/not an employer decision/i)).toBeVisible();
        await expectNoHorizontalOverflow(page);
        await capture(page, "responsive-mobile-390-job-detail-recruiter-lens-dark-reduced-motion");
      }
    });
  }
});
