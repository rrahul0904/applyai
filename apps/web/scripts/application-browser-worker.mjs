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

const headers = {
  "content-type": "application/json",
  "x-applyai-internal-token": INTERNAL_TOKEN,
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function api(path, init = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...headers, ...(init.headers || {}) },
  });
  if (!response.ok) {
    const payload = await response.text().catch(() => "");
    throw new Error(`ApplyAI API ${response.status}: ${payload.slice(0, 1000)}`);
  }
  return response.status === 204 ? null : response.json();
}

function normalized(value) {
  return String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
}

async function hasSecurityChallenge(page) {
  const selectors = [
    'iframe[src*="recaptcha"]',
    'iframe[src*="hcaptcha"]',
    '[data-sitekey]',
    '.g-recaptcha',
    '.h-captcha',
    'input[name*="captcha" i]',
  ];
  for (const selector of selectors) {
    if (await page.locator(selector).count()) return true;
  }
  const text = normalized(await page.locator("body").innerText().catch(() => ""));
  return [
    "verify you are human",
    "security challenge",
    "complete the captcha",
    "captcha verification",
    "cloudflare verification",
  ].some((phrase) => text.includes(phrase));
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
    candidates.push(page.locator(`#${CSS.escape(id)}`));
    candidates.push(page.locator(`[name="${CSS.escape(id)}"]`));
  }

  for (const locator of candidates) {
    if (await locator.count()) return locator.first();
  }

  if (label) {
    const needle = normalized(label);
    const controls = page.locator("input, textarea, select");
    const count = Math.min(await controls.count(), 250);
    for (let i = 0; i < count; i += 1) {
      const control = controls.nth(i);
      const attrs = await control.evaluate((element) => ({
        name: element.getAttribute("name") || "",
        id: element.getAttribute("id") || "",
        placeholder: element.getAttribute("placeholder") || "",
        aria: element.getAttribute("aria-label") || "",
      })).catch(() => null);
      if (!attrs) continue;
      const haystack = normalized(`${attrs.name} ${attrs.id} ${attrs.placeholder} ${attrs.aria}`);
      if (haystack && (haystack.includes(needle) || needle.includes(haystack))) return control;
    }
  }
  return null;
}

async function selectMatchingOption(locator, value) {
  const target = normalized(value);
  const options = await locator.locator("option").evaluateAll((items) =>
    items.map((item) => ({ value: item.value, label: item.textContent || "" })),
  );
  const exact = options.find((option) => normalized(option.label) === target || normalized(option.value) === target);
  const fuzzy = exact || options.find((option) => normalized(option.label).includes(target) || target.includes(normalized(option.label)));
  if (!fuzzy) return false;
  await locator.selectOption(fuzzy.value);
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
  const type = await control.getAttribute("type");
  const value = String(field.value);

  if (type === "file") {
    return { field_id: field.field_id, status: "FILE_UPLOAD_REQUIRED" };
  }
  if (tag === "select") {
    const selected = await selectMatchingOption(control, value);
    return { field_id: field.field_id, status: selected ? "FILLED" : "OPTION_NOT_FOUND" };
  }
  if (type === "checkbox") {
    const shouldCheck = ["true", "yes", "1", "checked"].includes(normalized(value));
    if (shouldCheck) await control.check();
    else await control.uncheck();
    return { field_id: field.field_id, status: "FILLED" };
  }
  if (type === "radio") {
    const label = page.getByLabel(value, { exact: false });
    if (await label.count()) {
      await label.first().check();
      return { field_id: field.field_id, status: "FILLED" };
    }
    return { field_id: field.field_id, status: "OPTION_NOT_FOUND" };
  }

  await control.fill(value);
  return { field_id: field.field_id, status: "FILLED" };
}

async function clickNextOrSubmit(page) {
  const submitNames = [/submit application/i, /^submit$/i, /^apply$/i, /complete application/i, /send application/i];
  for (const pattern of submitNames) {
    const button = page.getByRole("button", { name: pattern });
    if (await button.count()) {
      await button.first().click();
      return "SUBMIT";
    }
  }
  const inputSubmit = page.locator('input[type="submit"]');
  if (await inputSubmit.count()) {
    await inputSubmit.first().click();
    return "SUBMIT";
  }
  const nextNames = [/save and continue/i, /^continue$/i, /^next$/i, /review application/i];
  for (const pattern of nextNames) {
    const button = page.getByRole("button", { name: pattern });
    if (await button.count()) {
      await button.first().click();
      return "NEXT";
    }
  }
  return "NONE";
}

async function confirmationDetected(page, beforeUrl) {
  await page.waitForLoadState("domcontentloaded", { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1200);
  const url = page.url();
  const text = normalized(await page.locator("body").innerText().catch(() => ""));
  const confirmationPhrases = [
    "application submitted",
    "application has been submitted",
    "thank you for applying",
    "thanks for applying",
    "we received your application",
    "your application was received",
    "submission complete",
  ];
  const phrase = confirmationPhrases.find((item) => text.includes(item));
  const urlSignal = url !== beforeUrl && /(thank|confirm|complete|submitted|success)/i.test(url);
  return {
    confirmed: Boolean(phrase || urlSignal),
    url,
    text: text.slice(0, 4000),
    signal: phrase || (urlSignal ? "CONFIRMATION_URL" : null),
  };
}

async function prepareGreenhouse(page) {
  const application = page.locator("#application, form#application_form, form[action*='applications']");
  if (await application.count()) return;
  const apply = page.getByRole("button", { name: /apply/i }).or(page.getByRole("link", { name: /apply/i }));
  if (await apply.count()) await apply.first().click();
}

async function prepareLever(page) {
  const apply = page.getByRole("link", { name: /apply for this job|apply/i });
  if (await apply.count()) await apply.first().click();
}

async function prepareDriver(page, provider) {
  if (provider === "GREENHOUSE") return prepareGreenhouse(page);
  if (provider === "LEVER") return prepareLever(page);
}

async function executeOne(browser, execution) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const results = [];
  let submitted = false;

  try {
    await page.goto(execution.target_url, { waitUntil: "domcontentloaded", timeout: 45000 });
    await prepareDriver(page, execution.ats_provider);

    for (let pageNumber = 0; pageNumber < 12; pageNumber += 1) {
      if (await hasSecurityChallenge(page)) {
        return {
          status: "HUMAN_ACTION_REQUIRED",
          field_results: results,
          validation: { reason: "SECURITY_CHALLENGE", page_number: pageNumber },
          human_action: {
            reason: "SECURITY_CHALLENGE",
            message: "Complete the CAPTCHA or security challenge in the browser, then resume the application.",
            url: page.url(),
          },
        };
      }

      for (const field of execution.fields) {
        if (results.some((result) => result.field_id === field.field_id && result.status === "FILLED")) continue;
        const result = await fillField(page, field);
        if (!["OPTIONAL_NOT_FOUND", "MISSING_CONTROL"].includes(result.status)) results.push(result);
      }

      const uploadRequired = results.find((item) => item.status === "FILE_UPLOAD_REQUIRED");
      if (uploadRequired) {
        return {
          status: "HUMAN_ACTION_REQUIRED",
          field_results: results,
          validation: { reason: "FILE_UPLOAD_REQUIRED" },
          human_action: {
            reason: "FILE_UPLOAD_REQUIRED",
            message: "This employer requires a file upload that is not yet available to the browser worker as a secure file handle.",
            field_id: uploadRequired.field_id,
            url: page.url(),
          },
        };
      }

      const requiredMissing = execution.fields.filter((field) => field.required).filter((field) =>
        results.some((result) => result.field_id === field.field_id && ["MISSING_CONTROL", "OPTION_NOT_FOUND"].includes(result.status)),
      );
      if (requiredMissing.length) {
        return {
          status: "HUMAN_ACTION_REQUIRED",
          field_results: results,
          validation: { reason: "REQUIRED_FIELD_MAPPING_FAILED", fields: requiredMissing.map((field) => field.field_id) },
          human_action: {
            reason: "REQUIRED_FIELD_MAPPING_FAILED",
            message: "One or more required employer fields could not be mapped safely.",
            fields: requiredMissing.map((field) => ({ field_id: field.field_id, label: field.label })),
            url: page.url(),
          },
        };
      }

      const beforeUrl = page.url();
      const action = await clickNextOrSubmit(page);
      if (action === "NONE") break;
      if (action === "SUBMIT") submitted = true;

      const confirmation = await confirmationDetected(page, beforeUrl);
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
          confirmation_url: page.url(),
          confirmation_text: confirmation.text,
        };
      }
    }

    return {
      status: "HUMAN_ACTION_REQUIRED",
      field_results: results,
      validation: { reason: "NO_SAFE_SUBMIT_CONTROL" },
      human_action: {
        reason: "NO_SAFE_SUBMIT_CONTROL",
        message: "ApplyAI filled the fields it could verify, but could not identify a safe next or submit action.",
        url: page.url(),
      },
    };
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

async function complete(executionId, result) {
  return api(`/api/v1/internal/application-agent/executions/${executionId}/complete`, {
    method: "POST",
    body: JSON.stringify(result),
  });
}

async function work(browser) {
  const payload = await api("/api/v1/internal/application-agent/executions/next");
  const execution = payload?.execution;
  if (!execution) return false;
  console.log(`Application worker claimed ${execution.id} (${execution.ats_provider})`);
  const result = await executeOne(browser, execution);
  await complete(execution.id, result);
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
