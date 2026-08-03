import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

const demoCaptureDir = process.env.DEMO_CAPTURE_DIR;

async function captureDemo(page: Page, fileName: string) {
  if (!demoCaptureDir) return;

  mkdirSync(demoCaptureDir, { recursive: true });
  await page.screenshot({
    path: join(demoCaptureDir, `${fileName}.png`),
  });
}

test("candidate-first demo explains fit, truthful tailoring, and application planning", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/demo");

  await expect(
    page.getByRole("heading", { name: "Good evening, Alex." }),
  ).toBeVisible();
  await expect(page.getByText("These 3 are genuinely worth your time.")).toBeVisible();
  await expect(page.getByText("94%", { exact: true }).first()).toBeVisible();
  await captureDemo(page, "13-candidate-value-overview");

  await page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: "Senior Manager, Data Platform" }) })
    .getByRole("button", { name: "Review match" })
    .click();

  await expect(
    page.getByRole("heading", { name: "This role aligns closely with your next move." }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Why you fit" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What to address" })).toBeVisible();
  await expect(page.getByText("Verified company posting")).toBeVisible();
  await captureDemo(page, "14-candidate-match-explanation");

  await page.getByRole("button", { name: "Tailor resume truthfully" }).click();
  await expect(
    page.getByRole("heading", { name: "Tailor your resume without inventing anything." }),
  ).toBeVisible();
  await expect(page.getByText("Every claim must trace to your profile")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByRole("button", { name: "Approved" }).first()).toBeVisible();
  await captureDemo(page, "15-truthful-resume-tailoring");

  await page.getByRole("button", { name: /Use \d approved edits/ }).click();
  await page.getByRole("button", { name: "Add to application plan" }).click();
  await expect(
    page.getByRole("heading", { name: "Know exactly what needs your attention." }),
  ).toBeVisible();
  await expect(page.getByText("Senior Manager, Data Platform")).toBeVisible();
  await captureDemo(page, "16-application-plan");
});
