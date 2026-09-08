import { expect, test, type Page } from "@playwright/test";

const candidateTicket = process.env.APPLYAI_CLERK_SIGN_IN_TOKEN;
const expectedCandidateEmail = process.env.APPLYAI_PRODUCTION_TEST_EMAIL;
const operatorTicket = process.env.APPLYAI_CLERK_OPERATOR_SIGN_IN_TOKEN;
const operatorEmail = process.env.APPLYAI_PRODUCTION_OPERATOR_EMAIL;

async function signInWithTicket(page: Page, ticket: string) {
  await page.goto("/");
  await page.waitForFunction(
    () => Boolean((window as unknown as { Clerk?: { loaded?: boolean } }).Clerk?.loaded),
    undefined,
    { timeout: 30_000 },
  );

  return page.evaluate(async (signInTicket) => {
    const clerk = (
      window as unknown as {
        Clerk: {
          client: {
            signIn: {
              create(params: {
                strategy: "ticket";
                ticket: string;
              }): Promise<{
                status: string;
                createdSessionId?: string | null;
              }>;
            };
          };
          setActive(params: { session: string }): Promise<void>;
        };
      }
    ).Clerk;

    const attempt = await clerk.client.signIn.create({
      strategy: "ticket",
      ticket: signInTicket,
    });
    if (attempt.status !== "complete" || !attempt.createdSessionId) {
      return { status: attempt.status, sessionCreated: false };
    }
    await clerk.setActive({ session: attempt.createdSessionId });
    return { status: attempt.status, sessionCreated: true };
  }, ticket);
}

test.describe("production Clerk acceptance", () => {
  test("one-time Clerk ticket establishes a real candidate session that reaches FastAPI", async ({ page }) => {
    test.skip(
      !candidateTicket || !expectedCandidateEmail,
      "Production candidate Clerk acceptance credentials are not configured.",
    );

    const signIn = await signInWithTicket(page, candidateTicket!);
    expect(signIn).toEqual({ status: "complete", sessionCreated: true });

    await page.goto("/dashboard");
    await expect(page).not.toHaveURL(/\/sign-in(?:\/|\?|$)/);

    const identity = await page.evaluate(async () => {
      const response = await fetch("/api/backend/me", {
        cache: "no-store",
        credentials: "same-origin",
      });
      return {
        status: response.status,
        body: await response.json().catch(() => null),
      };
    });

    expect(identity.status).toBe(200);
    expect(identity.body).toEqual(
      expect.objectContaining({
        email: expectedCandidateEmail,
      }),
    );
  });

  test("existing Clerk operator reaches the API-enforced Operations control plane", async ({ page }) => {
    test.skip(
      !operatorTicket || !operatorEmail,
      "Production operator acceptance was not requested.",
    );

    const signIn = await signInWithTicket(page, operatorTicket!);
    expect(signIn).toEqual({ status: "complete", sessionCreated: true });

    await page.goto("/admin/operations");
    await expect(page.getByRole("heading", { name: "ApplyAI Operations Control" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sources", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ingestion", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Certification", exact: true })).toBeVisible();
  });
});
