import { expect, test, type Page } from "@playwright/test";

const candidate = "e2e.candidate@example.test";

async function signIn(page: Page) {
  await page.goto("/dev-login");
  await page.getByLabel("Test candidate email").fill(candidate);
  await page.getByRole("button", { name: "Sign in to development" }).click();
  await page.waitForURL(/\/(onboarding|dashboard)$/);
  await page.goto("/demo");
  await page.waitForURL(/\/dashboard$/);
}

async function expectAccessibleShell(page: Page) {
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator("h1, h2").first()).toBeVisible();

  const violations = await page.evaluate(() => {
    const visible = (element: Element) => {
      const html = element as HTMLElement;
      const style = window.getComputedStyle(html);
      return style.visibility !== "hidden" && style.display !== "none" && html.getClientRects().length > 0;
    };
    const labelText = (element: Element) => {
      const html = element as HTMLElement;
      const id = html.id;
      const explicit = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`)?.textContent : "";
      const wrapping = html.closest("label")?.textContent ?? "";
      return [
        element.getAttribute("aria-label"),
        element.getAttribute("aria-labelledby"),
        element.getAttribute("title"),
        explicit,
        wrapping,
        html.textContent,
      ]
        .filter(Boolean)
        .join(" ")
        .trim();
    };

    return Array.from(
      document.querySelectorAll("button, a[href], input, select, textarea"),
    )
      .filter(visible)
      .filter((element) => {
        const input = element as HTMLInputElement;
        if (input.type === "hidden") return false;
        return labelText(element).length === 0;
      })
      .map((element) => ({
        tag: element.tagName.toLowerCase(),
        id: (element as HTMLElement).id || null,
        className: (element as HTMLElement).className || null,
      }));
  });

  expect(violations, "Every visible interactive control needs an accessible name").toEqual([]);

  await page.keyboard.press("Tab");
  const focus = await page.evaluate(() => {
    const active = document.activeElement as HTMLElement | null;
    return active
      ? { tag: active.tagName.toLowerCase(), name: active.getAttribute("aria-label") || active.textContent || "" }
      : null;
  });
  expect(focus).not.toBeNull();
  expect(["a", "button", "input", "select", "textarea"]).toContain(focus?.tag);
}

test("core candidate journeys retain semantic and keyboard-accessible shells", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);

  for (const route of ["/dashboard", "/jobs", "/applications"]) {
    await test.step(route, async () => {
      await page.goto(route);
      await expectAccessibleShell(page);
    });
  }
});

test("mobile candidate shell remains keyboard reachable without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);
  await page.goto("/jobs");

  const dimensions = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 1);

  const mobileNav = page.locator(".cx-mobile-nav");
  await expect(mobileNav).toBeVisible();
  const links = mobileNav.getByRole("link");
  expect(await links.count()).toBeGreaterThan(1);
  for (let index = 0; index < Math.min(await links.count(), 5); index += 1) {
    const link = links.nth(index);
    await expect(link).toHaveAccessibleName(/.+/);
  }
});
