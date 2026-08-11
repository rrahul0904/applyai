import { chromium } from "@playwright/test";

const API_URL = (process.env.APPLYAI_API_URL || "http://localhost:8000").replace(/\/$/, "");
const INTERNAL_TOKEN = process.env.APPLYAI_INTERNAL_TOKEN || "";
const POLL_MS = Number(process.env.APPLYAI_APPLICATION_WORKER_POLL_MS || 3000);
const HEADLESS = process.env.APPLYAI_APPLICATION_WORKER_HEADLESS !== "false";
const ONCE = process.argv.includes("--once");

if (!INTERNAL_TOKEN) {
  console.error("APPLYAI_INTERNAL_TOKEN is required");
  process.exit(1);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const norm = (value) => String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
const attr = (name, value) => `[${name}=${JSON.stringify(String(value))}]`;

async function api(path, init = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-applyai-internal-token": INTERNAL_TOKEN,
      ...(init.headers || {}),
    },
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`ApplyAI API ${response.status}: ${body.slice(0, 1000)}`);
  }
  return response.status === 204 ? null : response.json();
}

async function hasSecurityChallenge(page) {
  for (const selector of [
    'iframe[src*="recaptcha"]',
    'iframe[src*="hcaptcha"]',
    '[data-sitekey]',
    '.g-recaptcha',
    '.h-captcha',
    'input[name*="captcha" i]',
  ]) {
    if (await page.locator(selector).count()) return true;
  }
  const body = norm(await page.locator("body").innerText().catch(() => ""));
  return [
    "verify you are human",
    "security challenge",
    "complete the captcha",
    "captcha verification",
    "cloudflare verification",
  ].some((phrase) => body.includes(phrase));
}

async function findControl(page, field) {
  const label = String(field.label || "").trim();
  const id = String(field.field_id || "").trim();
  const candidates = [];
  if (label) {
    candidates.push(page.getByLabel(label, { exact: true }));
    candidates.push(page.getByLabel(label, { exact: false }));
    candidates.push(page.getByRole("textbox", { name: label, exact: false }));
    candidates.push(page.getByRole("combobox", { name: label, exact: false }));
  }
  if (id) {
    candidates.push(page.locator(attr("id", id)));
    candidates.push(page.locator(attr("name", id)));
  }
  for (const locator of candidates) {
    if (await locator.count()) return locator.first();
  }

  if (!label) return null;
  const needle = norm(label);
  const controls = page.locator("input, textarea, select");
  const count = Math.min(await controls.count(), 250);
  for (let index = 0; index < count; index += 1) {
    const control = controls.nth(index);
    const hints = await control.evaluate((element) => [
      element.getAttribute("name") || "",
      element.getAttribute("id") || "",
      element.getAttribute("placeholder") || "",
      element.getAttribute("aria-label") || "",
    ].join(" ")).catch(() => "");
    const haystack = norm(hints);
    if (haystack && (haystack.includes(needle) || needle.includes(haystack))) return control;
  }
  return null;
}

async function selectOption(locator, value) {
  const target = norm(value);
  const options = await locator.locator("option").evaluateAll((items) =>
    items.map((item) => ({ value: item.value, label: item.textContent || "" })),
  );
  const match = options.find((option) => norm(option.label) === target || norm(option.value) === target)
    || options.find((option) => norm(option.label).includes(target) || target.includes(norm(option.label)));
  if (!match) return false;
  await locator.selectOption(match.value);
  return true;
}

async function fillField(page, field) {
  if (field.value === null || field.value === undefined || String(field.value).trim() === "") {
    return { field_id: field.field_id, status: "SKIPPED_EMPTY" };
  }
  const control = await findControl(page, field);
  if (!control) {
    return { field_id: field.field_id, status: field.required ? "MISSING_CONTROL" : "OPTIONAL_NOT_FOUND" };
  }
  const tag = await control.evaluate((element) => element.tagName.toLowerCase());
  const type = (await control.getAttribute("type")) || "";
  const value = String(field.value);

  if (type === "file") return { field_id: field.field_id, status: "FILE_UPLOAD_REQUIRED" };
  if (tag === "select") {
    return { field_id: field.field_id, status: (await selectOption(control, value)) ? "FILLED" : "OPTION_NOT_FOUND" };
  }
  if (type === "checkbox") {
    const checked = ["true", "yes", "1", "checked"].includes(norm(value));
    if (checked) await control.check();
    else await control.uncheck();
    return { field_id: field.field_id, status: "FILLED" };
  }
  if (type === "radio") {
    const choice = page.getByLabel(value, { exact: false });
    if (await choice.count()) {
      await choice.first().check();
      return { field_id: field.field_id, status: "FILLED" };
    }
    return { field_id: field.field_id, status: "OPTION_NOT_FOUND" };
  }
  await control.fill(value);
  return { field_id: field.field_id, status: "FILLED" };
}

async function prepareProvider(page, provider) {
  if (provider === "GREENHOUSE") {
    if (await page.locator("#application, form#application_form").count()) return;
    const button = page.getByRole("button", { name: /apply/i });
    const link = page.getByRole("link", { name: /apply/i });
    if (await button.count()) await button.first().click();
    else if (await link.count()) await link.first().click();
  }
  if (provider === "LEVER") {
    const link = page.getByRole("link", { name: /apply for this job|apply/i });
    if (await link.count()) await link.first().click();
  }
}

async function nextAction(page) {
  for (const pattern of [/submit application/i, /^submit$/i, /^apply$/i, /complete application/i, /send application/i]) {
    const button = page.getByRole("button", { name: pattern });
    if (await button.count()) {
      await button.first().click();
      return "SUBMIT";
    }
  }
  const submit = page.locator('input[type="submit"]');
  if (await submit.count()) {
    await submit.first().click();
    return "SUBMIT";
  }
  for (const pattern of [/save and continue/i, /^continue$/i, /^next$/i, /review application/i]) {
    const button = page.getByRole("button", { name: pattern });
    if (await button.count()) {
      await button.first().click();
      return "NEXT";
    }
  }
  return "NONE";
}

async function detectConfirmation(page, priorUrl) {
  await page.waitForLoadState("domcontentloaded", { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1200);
  const url = page.url();
  const body = norm(await page.locator("body").innerText().catch(() => ""));
  const phrase = [
    "application submitted",
    "application has been submitted",
    "thank you for applying",
    "thanks for applying",
    "we received your application",
    "your application was received",
    "submission complete",
  ].find((item) => body.includes(item));
  const urlSignal = url !== priorUrl && /(thank|confirm|complete|submitted|success)/i.test(url);
  return { confirmed: Boolean(phrase || urlSignal), url, text: body.slice(0, 4000), signal: phrase || (urlSignal ? "CONFIRMATION_URL" : null) };
}

function human(reason, message, page, fieldResults, extra = {}) {
  return {
    status: "HUMAN_ACTION_REQUIRED",
    field_results: fieldResults,
    validation: { reason, ...extra },
    human_action: { reason, message, url: page.url(), ...extra },
  };
}

async function executeOne(browser, execution) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const results = [];
  let submitted = false;
  try {
    await page.goto(execution.target_url, { waitUntil: "domcontentloaded", timeout: 45000 });
    await prepareProvider(page, execution.ats_provider);

    for (let pageNumber = 0; pageNumber < 12; pageNumber += 1) {
      if (await hasSecurityChallenge(page)) {
        return human("SECURITY_CHALLENGE", "Complete the CAPTCHA or security challenge in the browser, then resume the application.", page, results, { page_number: pageNumber });
      }

      for (const field of execution.fields) {
        if (results.some((item) => item.field_id === field.field_id && item.status === "FILLED")) continue;
        const result = await fillField(page, field);
        if (!["OPTIONAL_NOT_FOUND", "MISSING_CONTROL"].includes(result.status)) results.push(result);
      }

      const upload = results.find((item) => item.status === "FILE_UPLOAD_REQUIRED");
      if (upload) {
        return human("FILE_UPLOAD_REQUIRED", "This employer requires a file upload that is not yet available to the browser worker as a secure file handle.", page, results, { field_id: upload.field_id });
      }

      const failedRequired = execution.fields.filter((field) => field.required).filter((field) =>
        results.some((item) => item.field_id === field.field_id && ["MISSING_CONTROL", "OPTION_NOT_FOUND"].includes(item.status)),
      );
      if (failedRequired.length) {
        return human("REQUIRED_FIELD_MAPPING_FAILED", "One or more required employer fields could not be mapped safely.", page, results, {
          fields: failedRequired.map((field) => ({ field_id: field.field_id, label: field.label })),
        });
      }

      const priorUrl = page.url();
      const action = await nextAction(page);
      if (action === "NONE") break;
      if (action === "SUBMIT") submitted = true;
      const confirmation = await detectConfirmation(page, priorUrl);
      if (confirmation.confirmed) {
        return {
          status: "CONFIRMED",
          field_results: results,
          validation: { confirmation_signal: confirmation.signal, provider: execution.ats_provider },
          confirmation_url: confirmation.url,
          confirmation_text: confirmation.text,
        };
      }
      if (submitted) {
        return {
          status: "SUBMITTED",
          field_results: results,
          validation: { confirmation_detected: false, provider: execution.ats_provider },
          confirmation_url: confirmation.url,
          confirmation_text: confirmation.text,
        };
      }
    }

    return human("NO_SAFE_SUBMIT_CONTROL", "ApplyAI filled the fields it could verify, but could not identify a safe next or submit action.", page, results);
  } catch (error) {
    return {
      status: "FAILED",
      field_results: results,
      validation: { submitted },
      error_code: "BROWSER_EXECUTION_FAILED",
      error_detail: error instanceof Error ? error.message.slice(0, 4000) : String(error).slice(0, 4000),
    };
  } finally {
    await context.close();
  }
}

async function work(browser) {
  const payload = await api("/api/v1/internal/application-agent/executions/next");
  const execution = payload?.execution;
  if (!execution) return false;
  console.log(`Application worker claimed ${execution.id} (${execution.ats_provider})`);
  const result = await executeOne(browser, execution);
  await api(`/api/v1/internal/application-agent/executions/${execution.id}/complete`, {
    method: "POST",
    body: JSON.stringify(result),
  });
  console.log(`Application worker completed ${execution.id}: ${result.status}`);
  return true;
}

const browser = await chromium.launch({ headless: HEADLESS });
try {
  do {
    const handled = await work(browser).catch((error) => {
      console.error(error);
      return false;
    });
    if (ONCE) break;
    if (!handled) await sleep(POLL_MS);
  } while (true);
} finally {
  await browser.close();
}
