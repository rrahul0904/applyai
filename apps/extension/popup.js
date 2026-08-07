const baseInput = document.getElementById("base");
const status = document.getElementById("status");

chrome.storage.sync.get({ applyaiBaseUrl: "http://localhost:3000" }, ({ applyaiBaseUrl }) => {
  baseInput.value = applyaiBaseUrl;
});

document.getElementById("save").addEventListener("click", async () => {
  const base = baseInput.value.trim().replace(/\/$/, "");
  if (!/^https?:\/\//i.test(base)) {
    status.textContent = "Enter a valid ApplyAI URL.";
    return;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url || !/^https?:\/\//i.test(tab.url)) {
    status.textContent = "The current tab is not a public web page.";
    return;
  }
  await chrome.storage.sync.set({ applyaiBaseUrl: base });
  const destination = `${base}/import-job?url=${encodeURIComponent(tab.url)}`;
  await chrome.tabs.create({ url: destination });
  window.close();
});
