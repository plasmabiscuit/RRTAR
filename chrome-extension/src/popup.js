const statusEl = document.querySelector("#status");
const previewEl = document.querySelector("#preview");
const formChipEl = document.querySelector("#form-chip");
const openDashboardBtn = document.querySelector("#open-dashboard-btn");
const autofillBtn = document.querySelector("#autofill-btn");
const optionsBtn = document.querySelector("#options-btn");

let currentDetection = null;
let currentPayload = null;
let currentPreviewBundle = null;
const FORM_CHIP_LABELS = {
  keyperson: "Key Person",
  budget: "Budget",
  "performance-site": "Perf. Site",
};

autofillBtn.disabled = true;
autofillBtn.classList.add("btn-disabled");

openDashboardBtn.addEventListener("click", async () => {
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:open-dashboard",
    formType: currentDetection?.formType || "keyperson",
  });
  if (!result?.ok) {
    setStatus(result?.error || "Could not open dashboard.", "err");
  }
});

autofillBtn.addEventListener("click", async () => {
  await detectAndLoad({ silentSuccess: true, skipManifestReload: true });
  if (!currentDetection?.supported) {
    setStatus("No supported Grants.gov form detected in the active tab.", "warn");
    return;
  }
  if (!currentPreviewBundle?.ok) {
    setStatus("No compatible Grants.gov form is ready in the active tab.", "warn");
    return;
  }
  if (currentDetection.formType !== currentPreviewBundle.formType) {
    setStatus(`Manifest form ${currentPreviewBundle.formType} does not match detected form ${currentDetection.formType}.`, "warn");
    refreshAutofillState();
    return;
  }

  setStatus(`Preparing ${currentPreviewBundle.formType} manifest for automation...`, "pend");
  const prepared = await chrome.runtime.sendMessage({
    type: "rrtar:prepare-autofill",
    formType: currentDetection.formType,
  });
  if (!prepared?.ok) {
    currentPayload = null;
    setStatus(formatObject(prepared), "err");
    refreshAutofillState();
    return;
  }
  currentPayload = prepared;

  const tab = await getActiveTab();
  if (!tab?.id) {
    setStatus("No active tab.", "err");
    return;
  }

  setStatus(`Autofilling ${currentPayload.formType} from extension dashboard manifest...`, "pend");
  try {
    const autofillResult = await chrome.tabs.sendMessage(tab.id, {
      type: "rrtar:autofill-manifest",
      payload: currentPayload,
    });
    setStatus(formatObject(autofillResult), autofillResult?.ok ? "ok" : "err");
  } catch (_error) {
    setStatus("Could not reach the Grants.gov form in the active tab.", "err");
  }
});

optionsBtn.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

init();

async function init() {
  await detectAndLoad();
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0] || null;
}

function isGrantsGovTab(tab) {
  const url = String(tab?.url || "").trim();
  if (!url) {
    return false;
  }
  try {
    const parsed = new URL(url);
    return parsed.hostname === "grants.gov" || parsed.hostname.endsWith(".grants.gov");
  } catch {
    return false;
  }
}

async function detectAndLoad({ silentSuccess = false, skipManifestReload = false } = {}) {
  setFormChip("Scanning", "pend");
  setStatus("Checking the active Grants.gov tab and loading the current manifest...", "pend");

  const tab = await getActiveTab();
  if (!tab?.id) {
    currentDetection = null;
    currentPayload = null;
    currentPreviewBundle = null;
    renderPreview(null, null);
    setFormChip("No tab", "err");
    setStatus("No active tab.", "err");
    refreshAutofillState();
    return;
  }

  if (!isGrantsGovTab(tab)) {
    currentDetection = null;
    currentPayload = null;
    currentPreviewBundle = null;
    renderPreview(null, null);
    setFormChip("Offsite", "warn");
    setStatus("Active tab is not a grants.gov page.", "warn");
    refreshAutofillState();
    return;
  }

  let response;
  try {
    response = await chrome.tabs.sendMessage(tab.id, { type: "rrtar:detect-form" });
  } catch (_error) {
    currentDetection = null;
    currentPayload = null;
    currentPreviewBundle = null;
    renderPreview(null, null);
    setFormChip("No form", "warn");
    setStatus("No supported Grants.gov form detected in the active tab.", "warn");
    refreshAutofillState();
    return;
  }

  if (!response?.ok) {
    currentDetection = null;
    currentPayload = null;
    currentPreviewBundle = null;
    renderPreview(null, null);
    setFormChip("Error", "err");
    setStatus(response?.error || "Could not detect form.", "err");
    refreshAutofillState();
    return;
  }

  currentDetection = response.detection;
  if (!currentDetection?.supported) {
    currentPayload = null;
    currentPreviewBundle = null;
    renderPreview(null, currentDetection);
    setFormChip("No form", "warn");
    setStatus("No supported Grants.gov form detected in the active tab.", "warn");
    refreshAutofillState();
    return;
  }

  setFormChip(shortFormLabel(currentDetection), "ok");
  currentPayload = null;

  if (skipManifestReload && currentPreviewBundle?.ok && currentPreviewBundle.formType === currentDetection.formType) {
    renderPreview(currentPreviewBundle, currentDetection);
    refreshAutofillState();
    if (!silentSuccess) {
      setStatus(`Detected ${currentDetection.label || currentDetection.formType}.`, "ok");
    }
    return;
  }

  setStatus(`Detected ${currentDetection.label || currentDetection.formType}. Loading the current dashboard manifest...`, "pend");
  const bundleResult = await chrome.runtime.sendMessage({
    type: "rrtar:get-dashboard-state",
    formType: currentDetection.formType,
  });

  if (!bundleResult?.ok) {
    currentPreviewBundle = null;
    renderPreview(null, currentDetection);
    setStatus(formatObject(bundleResult), "err");
    refreshAutofillState();
    return;
  }

  currentPreviewBundle = bundleResult;
  renderPreview(bundleResult, currentDetection);
  refreshAutofillState();
  if (!silentSuccess) {
    setStatus(`Loaded current ${bundleResult.formType} manifest from extension dashboard.`, "ok");
  }
}

function setStatus(text, tone = "pend") {
  statusEl.textContent = text;
  statusEl.className = `card status-card ${tone}`;
}

function setFormChip(text, tone = "pend") {
  formChipEl.textContent = text;
  formChipEl.className = `badge ${tone}`;
}

function shortFormLabel(detection) {
  return FORM_CHIP_LABELS[detection?.formType] || detection?.label || detection?.formType || "Unknown";
}

function renderPreview(bundle, detection) {
  if (!bundle?.ok) {
    previewEl.textContent = detection?.supported
      ? `${detection.label || detection.formType}\n\nOpen Dashboard to review or import the matching manifest before running automation.`
      : "Open a supported Grants.gov form to auto-load the matching manifest.\n\nSupported: R&R Senior/Key Person, R&R Budget, Project/Performance Site.";
    return;
  }

  const lines = [
    `Form: ${detection?.label || bundle.formType}`,
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
    currentPreviewBundle?.ok &&
    Array.isArray(currentPreviewBundle?.manifest) &&
    currentPreviewBundle.manifest.length > 0 &&
    currentDetection?.supported &&
    currentPreviewBundle.formType === currentDetection.formType,
  );
  autofillBtn.disabled = !canRun;
  autofillBtn.classList.toggle("btn-disabled", !canRun);
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
