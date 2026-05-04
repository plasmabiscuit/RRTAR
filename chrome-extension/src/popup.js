const statusEl = document.querySelector("#status");
const jobIdInput = document.querySelector("#job-id");
const detectBtn = document.querySelector("#detect-btn");
const autofillBtn = document.querySelector("#autofill-btn");
const optionsBtn = document.querySelector("#options-btn");

detectBtn.addEventListener("click", async () => {
  setStatus("Detecting current Grants.gov form...");
  const tab = await getActiveTab();
  if (!tab?.id) {
    setStatus("No active tab.");
    return;
  }

  const response = await chrome.tabs.sendMessage(tab.id, { type: "rrtar:detect-form" });
  if (!response?.ok) {
    setStatus(response?.error || "Could not detect form.");
    return;
  }

  const detection = response.detection;
  if (!detection.supported) {
    setStatus("No supported form detected in this tab.");
    return;
  }

  setStatus(`Detected form: ${detection.formType}\niframe: ${detection.iframeSrc}`);
});

autofillBtn.addEventListener("click", async () => {
  const jobId = jobIdInput.value.trim();
  if (!jobId) {
    setStatus("Job ID is required.");
    return;
  }

  setStatus(`Fetching manifest for job ${jobId}...`);
  const manifestResult = await chrome.runtime.sendMessage({
    type: "rrtar:fetch-manifest",
    jobId,
  });

  if (!manifestResult?.ok) {
    setStatus(formatObject(manifestResult));
    return;
  }

  const tab = await getActiveTab();
  if (!tab?.id) {
    setStatus("No active tab.");
    return;
  }

  setStatus("Manifest loaded. Sending to page automation...");
  const autofillResult = await chrome.tabs.sendMessage(tab.id, {
    type: "rrtar:autofill-manifest",
    manifest: manifestResult.manifest,
  });
  setStatus(formatObject(autofillResult));
});

optionsBtn.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0] || null;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function formatObject(value) {
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
