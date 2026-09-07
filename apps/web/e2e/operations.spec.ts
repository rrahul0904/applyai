import { expect, test, type Page } from "@playwright/test";

const operatorEmail = "e2e.candidate@example.test";

async function signIn(page: Page) {
  await page.goto("/dev-login");
  await page.getByLabel("Test candidate email").fill(operatorEmail);
  await page.getByRole("button", { name: "Sign in to development" }).click();
  await page.waitForURL(/\/(onboarding|dashboard)$/);
}

test("admin/operations exposes durable jobs, sources, ingestion and certification controls", async ({ page }) => {
  await signIn(page);
  await page.goto("/admin/operations");

  await expect(page.getByRole("heading", { name: "ApplyAI Operations Control" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sources", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ingestion", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Certification", exact: true })).toBeVisible();

  await page.getByLabel("Release note").fill("Clean-room Operations browser certification.");
  await page.getByRole("button", { name: "Record PASS" }).click();
  await expect(page.getByText("Clean-room Operations browser certification.")).toBeVisible();
  await expect(page.getByText("PASS", { exact: true }).first()).toBeVisible();
});
