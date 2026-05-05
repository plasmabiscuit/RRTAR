const statusEl = document.querySelector("#status");
const previewEl = document.querySelector("#preview");
const detectBtn = document.querySelector("#detect-btn");
const openDashboardBtn = document.querySelector("#open-dashboard-btn");
const autofillBtn = document.querySelector("#autofill-btn");
const optionsBtn = document.querySelector("#options-btn");

let currentDetection = null;
let currentPayload = null;

autofillBtn.disabled = true;

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

  currentDetection = response.detection;
  if (!currentDetection.supported) {
    currentPayload = null;
    renderPreview(null);
    setStatus("No supported form detected in this tab.");
    refreshAutofillState();
    return;
  }

  setStatus(`Detected form: ${currentDetection.formType}\nLoading current dashboard manifest...`);
  const bundleResult = await chrome.runtime.sendMessage({
    type: "rrtar:prepare-autofill",
    formType: currentDetection.formType,
  });

  if (!bundleResult?.ok) {
    currentPayload = null;
    renderPreview(null);
    setStatus(formatObject(bundleResult));
    refreshAutofillState();
    return;
  }

  currentPayload = bundleResult;
  renderPreview(bundleResult);
  setStatus(`Loaded current ${bundleResult.formType} manifest from extension dashboard.`);
  refreshAutofillState();
});

openDashboardBtn.addEventListener("click", async () => {
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:open-dashboard",
    formType: currentDetection?.formType || "keyperson",
  });
  if (!result?.ok) {
    setStatus(result?.error || "Could not open dashboard.");
  }
});

autofillBtn.addEventListener("click", async () => {
  if (!currentPayload) {
    setStatus("Detect the current form first.");
    return;
  }
  if (!currentDetection?.supported) {
    setStatus("Detect the active Grants.gov form first.");
    return;
  }
  if (currentDetection.formType !== currentPayload.formType) {
    setStatus(`Manifest form ${currentPayload.formType} does not match detected form ${currentDetection.formType}.`);
    refreshAutofillState();
    return;
  }

  const tab = await getActiveTab();
  if (!tab?.id) {
    setStatus("No active tab.");
    return;
  }

  setStatus(`Autofilling ${currentPayload.formType} from extension dashboard manifest...`);
  const autofillResult = await chrome.tabs.sendMessage(tab.id, {
    type: "rrtar:autofill-manifest",
    payload: currentPayload,
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

function renderPreview(bundle) {
  if (!bundle?.ok) {
    previewEl.textContent = "Detect a Grants.gov form to load the current dashboard manifest.";
    return;
  }

  const lines = [
    `Form: ${bundle.formType}`,
    ...(Array.isArray(bundle.preview?.lines) ? bundle.preview.lines : []),
  ];

  const warnings = Array.isArray(bundle.preview?.warnings) ? bundle.preview.warnings : [];
  if (warnings.length) {
    lines.push("");
    lines.push("Warnings:");
    for (const warning of warnings.slice(0, 8)) {
      lines.push(`- ${warning}`);
    }
    if (warnings.length > 8) {
      lines.push(`- ... ${warnings.length - 8} more`);
    }
  }

  previewEl.textContent = lines.join("\n");
}

function refreshAutofillState() {
  const canRun = Boolean(
    currentPayload?.ok &&
    Array.isArray(currentPayload?.manifest) &&
    currentPayload.manifest.length > 0 &&
    currentDetection?.supported &&
    currentPayload.formType === currentDetection.formType,
  );
  autofillBtn.disabled = !canRun;
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
