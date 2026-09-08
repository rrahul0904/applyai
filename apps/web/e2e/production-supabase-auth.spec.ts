import { expect, test } from "@playwright/test";

const candidateEmail = process.env.APPLYAI_PRODUCTION_TEST_EMAIL;
const candidatePassword = process.env.APPLYAI_PRODUCTION_TEST_PASSWORD;
const operatorEmail = process.env.APPLYAI_PRODUCTION_OPERATOR_EMAIL;
const operatorAccessToken = process.env.APPLYAI_OPERATOR_ACCESS_TOKEN;
const operatorRefreshToken = process.env.APPLYAI_OPERATOR_REFRESH_TOKEN;

test("candidate password session reaches FastAPI, signs out, and can delete application data", async ({
  page,
}) => {
  test.skip(
    !candidateEmail || !candidatePassword,
    "Temporary production candidate credentials are not configured.",
  );

  await page.goto("/sign-in");
  await page.getByLabel("Email address").fill(candidateEmail!);
  await page.getByLabel("Password").fill(candidatePassword!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard(?:\?|$)/);

  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/backend/me", {
      credentials: "same-origin",
      cache: "no-store",
    });
    return {
      status: response.status,
      body: await response.json().catch(() => null),
    };
  });
  expect(identity.status).toBe(200);
  expect(identity.body).toEqual(
    expect.objectContaining({ email: candidateEmail }),
  );

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.goto("/sign-in");
  await page.getByLabel("Email address").fill(candidateEmail!);
  await page.getByLabel("Password").fill(candidatePassword!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard(?:\?|$)/);

  const deletion = await page.evaluate(async () => {
    const response = await fetch("/api/backend/account", {
      method: "DELETE",
      credentials: "same-origin",
      cache: "no-store",
    });
    return {
      status: response.status,
      body: await response.json().catch(() => null),
    };
  });
  expect(deletion.status).toBe(200);
  expect(deletion.body).toEqual(
    expect.objectContaining({
      deleted: true,
      application_data_deleted: true,
    }),
  );
});

test("existing Supabase operator reaches database-role Operations control plane", async ({
  context,
  page,
}) => {
  test.skip(
    !operatorEmail || !operatorAccessToken || !operatorRefreshToken,
    "Production operator session is not configured.",
  );

  const productionUrl = new URL(
    process.env.APPLYAI_PRODUCTION_URL ?? "https://applyai-gold.vercel.app",
  );
  const cookieBase = {
    domain: productionUrl.hostname,
    path: "/",
    httpOnly: true,
    secure: productionUrl.protocol === "https:",
    sameSite: "Lax" as const,
  };
  await context.addCookies([
    {
      ...cookieBase,
      name: "applyai_sb_access",
      value: operatorAccessToken!,
    },
    {
      ...cookieBase,
      name: "applyai_sb_refresh",
      value: operatorRefreshToken!,
    },
  ]);

  await page.goto("/admin/operations");
  await expect(
    page.getByRole("heading", { name: "ApplyAI Operations Control" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sources", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ingestion", exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Certification", exact: true }),
  ).toBeVisible();
});
