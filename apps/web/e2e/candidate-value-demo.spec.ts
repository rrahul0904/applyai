import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

const demoCaptureDir = process.env.DEMO_CAPTURE_DIR;

async function captureDemo(page: Page, fileName: string) {
  if (!demoCaptureDir) return;
  mkdirSync(demoCaptureDir, { recursive: true });
  await page.screenshot({
    path: join(demoCaptureDir, `${fileName}.png`),
    animations: "disabled",
  });
}

test("functional candidate workspace persists preferences, saves, tailoring, and application stages", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/demo");

  await expect(
    page.getByRole("heading", { name: "Good afternoon, Alex." }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Real API + PostgreSQL")).toBeVisible();
  await expect(page.getByRole("button", { name: "Review match" }).first()).toBeVisible();
  await captureDemo(page, "13-functional-workspace-overview");

  await page.getByRole("button", { name: "Edit preferences" }).click();
  await expect(
    page.getByRole("heading", { name: "What should ApplyAI optimize for?" }),
  ).toBeVisible();
  await page.getByLabel("Minimum compensation").fill("95000");
  await page.getByRole("button", { name: "Save and re-rank jobs" }).click();
  await expect(page.getByText("Matches re-ranked for your new goals")).toBeVisible();

  await page.getByRole("button", { name: "Review match" }).first().click();
  await expect(
    page.getByRole("heading", { name: "This score comes from your saved profile." }),
  ).toBeVisible();
  await expect(page.getByText("Why you fit")).toBeVisible();
  await expect(page.getByText("What to address")).toBeVisible();
  await captureDemo(page, "14-functional-match-explanation");

  const selectedTitle = await page.locator("h1").first().textContent();
  expect(selectedTitle).toBeTruthy();

  await page.getByRole("button", { name: "Save selected job" }).click();
  await expect(page.getByText("Job saved")).toBeVisible();

  await page.getByRole("button", { name: "Tailor resume truthfully" }).click();
  await expect(
    page.getByRole("heading", { name: "Tailor your resume without inventing anything." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).first().click();
  await page.getByRole("button", { name: "Save decisions" }).click();
  await expect(page.getByText("Resume decisions saved to the application")).toBeVisible();
  await captureDemo(page, "15-functional-resume-tailoring");

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Good afternoon, Alex." }),
  ).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Review match" }).first().click();
  await page.getByRole("button", { name: "Tailor resume truthfully" }).click();
  await expect(page.getByText("Edit 1 · approved")).toBeVisible();

  await page.getByRole("button", { name: /Use 1 approved edit/ }).click();
  await expect(
    page.getByRole("heading", { name: "Move every application forward." }),
  ).toBeVisible();
  await expect(page.getByText(selectedTitle as string).first()).toBeVisible();
  await captureDemo(page, "16-functional-application-tracker");

  await page.getByRole("button", { name: "Move forward →" }).first().click();
  await expect(page.getByText("Application stage updated")).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Good afternoon, Alex." }),
  ).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Applications" }).click();
  await expect(page.getByText(selectedTitle as string).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Applied" })).toBeVisible();
});
