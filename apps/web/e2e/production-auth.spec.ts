import { expect, test } from "@playwright/test";

const ticket = process.env.APPLYAI_CLERK_SIGN_IN_TOKEN;
const expectedEmail = process.env.APPLYAI_PRODUCTION_TEST_EMAIL;

test.describe("production Clerk acceptance", () => {
  test.skip(!ticket || !expectedEmail, "Production Clerk acceptance credentials are not configured.");

  test("one-time Clerk ticket establishes a real session that reaches FastAPI", async ({ page }) => {
    await page.goto("/");

    await page.waitForFunction(
      () => Boolean((window as unknown as { Clerk?: { loaded?: boolean } }).Clerk?.loaded),
      undefined,
      { timeout: 30_000 },
    );

    const signIn = await page.evaluate(async (signInTicket) => {
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
    }, ticket!);

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
        email: expectedEmail,
      }),
    );
  });
});
