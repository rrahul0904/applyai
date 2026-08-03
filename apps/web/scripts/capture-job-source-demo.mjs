import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

import { chromium } from "@playwright/test";

const baseUrl = process.env.DEMO_BASE_URL ?? "http://127.0.0.1:4173";
const outputDir = resolve(
  process.env.DEMO_SCREENSHOT_DIR ?? "../../artifacts/job-source-platform-demo/screenshots",
);

await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1100 },
  deviceScaleFactor: 1,
});

try {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.screenshot({
    path: resolve(outputDir, "01-platform-overview.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Dedup & provenance" }).click();
  await page.screenshot({
    path: resolve(outputDir, "02-dedup-provenance.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Execution evidence" }).click();
  await page.screenshot({
    path: resolve(outputDir, "03-execution-evidence.png"),
    fullPage: true,
  });
} finally {
  await browser.close();
}
