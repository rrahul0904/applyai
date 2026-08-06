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

async function completeCandidateReview(page: Page) {
  await page.getByRole("button", { name: "Tailor my resume" }).click();
  await expect(
    page.getByRole("heading", {
      name: /Make your verified experience clearer for/,
    }),
  ).toBeVisible();
  await captureDemo(page, "18-evidence-locked-resume-tailoring");

  const approveButtons = page.getByRole("button", { name: "Approve" });
  await approveButtons.nth(0).click();
  await approveButtons.nth(1).click();
  await page.getByRole("button", { name: "Reject" }).nth(2).click();
  await page
    .getByRole("button", { name: "Finalize approved resume edits" })
    .click();

  await expect(
    page.getByRole("heading", {
      name: "Review every word before the package is marked ready.",
    }),
  ).toBeVisible();
  await captureDemo(page, "19-application-assistant-review");

  const verificationBoxes = page.getByRole("checkbox");
  await expect(verificationBoxes).toHaveCount(4);
  for (let index = 0; index < 4; index += 1) {
    if (!(await verificationBoxes.nth(index).isChecked())) {
      await verificationBoxes.nth(index).check();
    }
  }

  await page.getByRole("button", { name: "Finalize reviewed package" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Your reviewed materials are organized and ready to use.",
    }),
  ).toBeVisible();
  await expect(page.getByText("100%", { exact: true })).toBeVisible();
  await expect(page.getByText("READY", { exact: true })).toBeVisible();
  await expect(page.getByText("External submission", { exact: true })).toBeVisible();
  await captureDemo(page, "20-ready-application-package");
}

test("realistic candidate beta journey persists the reviewed application package", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/beta");

  await expect(
    page.getByRole("heading", {
      name: "Apply to the right role with evidence you can defend.",
    }),
  ).toBeVisible();
  await expect(page.getByText(/confidence · .* fit/i).first()).toBeVisible();
  await expect(page.getByText("ROLE ALIGNMENT", { exact: true })).toBeVisible();
  await expect(page.getByText("VERIFIED SKILLS", { exact: true })).toBeVisible();
  await captureDemo(page, "17-ai-match-prioritization");

  await completeCandidateReview(page);

  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Apply to the right role with evidence you can defend.",
    }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Tailor my resume" }).click();
  await expect(page.getByText("APPROVED", { exact: true }).first()).toBeVisible();
  await page
    .getByRole("button", { name: "Finalize approved resume edits" })
    .click();

  await expect(page.getByText("100% ready", { exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox").first()).toBeChecked();
  await expect(page.getByRole("checkbox").nth(3)).toBeChecked();

  await page.getByRole("button", { name: "Finalize reviewed package" }).click();
  await expect(page.getByText("READY", { exact: true })).toBeVisible();
});
