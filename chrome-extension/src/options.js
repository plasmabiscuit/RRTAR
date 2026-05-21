const backendBaseUrlEl = document.querySelector("#backend-base-url");
const apiKeyEl = document.querySelector("#api-key");
const agencyEl = document.querySelector("#agency");
const saveSettingsBtn = document.querySelector("#save-settings-btn");
const testBackendBtn = document.querySelector("#test-backend-btn");
const openDashboardBtn = document.querySelector("#open-dashboard-btn");
const retroFontsToggleEl = document.querySelector("#retro-fonts-toggle");
const fontScaleEl = document.querySelector("#font-scale");
const fontScaleValueEl = document.querySelector("#font-scale-value");
const statusEl = document.querySelector("#status");

init();

async function init() {
  const result = await chrome.runtime.sendMessage({ type: "rrtar:get-settings" });
  if (!result?.ok) {
    statusEl.textContent = result?.error || "Could not load settings.";
    return;
  }
  backendBaseUrlEl.value = result.settings?.backendBaseUrl || "";
  apiKeyEl.value = result.settings?.apiKey || "";
  agencyEl.value = result.settings?.agency || "default";
  retroFontsToggleEl.checked = result.settings?.useRetroFonts !== false;
  fontScaleEl.value = String(result.settings?.fontScale || 1);
  updateFontScaleValue(fontScaleEl.value);
  applyFontSettings(result.settings);
}

retroFontsToggleEl.addEventListener("change", async () => {
  applyFontSettings({
    useRetroFonts: retroFontsToggleEl.checked,
    fontScale: fontScaleEl.value,
  });
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:set-settings",
    settings: { useRetroFonts: retroFontsToggleEl.checked },
  });
  statusEl.textContent = result?.ok
    ? `Retro fonts ${retroFontsToggleEl.checked ? "enabled" : "disabled"} for supported screens.`
    : result?.error || "Could not update font preference.";
});

fontScaleEl.addEventListener("input", () => {
  updateFontScaleValue(fontScaleEl.value);
  applyFontSettings({
    useRetroFonts: retroFontsToggleEl.checked,
    fontScale: fontScaleEl.value,
  });
});

fontScaleEl.addEventListener("change", async () => {
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:set-settings",
    settings: { fontScale: Number(fontScaleEl.value) },
  });
  statusEl.textContent = result?.ok
    ? `Font size set to ${formatFontScale(fontScaleEl.value)}.`
    : result?.error || "Could not update font size.";
});

saveSettingsBtn.addEventListener("click", async () => {
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:set-settings",
    settings: collectSettings(),
  });
  statusEl.textContent = result?.ok
    ? `Saved backend settings for ${result.settings.backendBaseUrl || "no backend URL"}.`
    : result?.error || "Could not save settings.";
});

testBackendBtn.addEventListener("click", async () => {
  statusEl.textContent = "Testing backend...";
  const saveResult = await chrome.runtime.sendMessage({
    type: "rrtar:set-settings",
    settings: collectSettings(),
  });
  if (!saveResult?.ok) {
    statusEl.textContent = saveResult?.error || "Could not save settings.";
    return;
  }
  const result = await chrome.runtime.sendMessage({ type: "rrtar:test-backend" });
  statusEl.textContent = result?.ok
    ? `Backend OK\nHealth: ${JSON.stringify(result.health)}\nContacts: ${result.reference?.contacts_count ?? "?"}`
    : result?.error || "Backend test failed.";
});

openDashboardBtn.addEventListener("click", async () => {
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:open-dashboard",
    formType: "keyperson",
  });
  statusEl.textContent = result?.ok ? "Dashboard opened." : result?.error || "Could not open dashboard.";
});

function collectSettings() {
  return {
    backendBaseUrl: backendBaseUrlEl.value,
    apiKey: apiKeyEl.value,
    agency: agencyEl.value,
    useRetroFonts: retroFontsToggleEl.checked,
    fontScale: Number(fontScaleEl.value),
  };
}

function applyFontSettings(settings) {
  document.body.classList.toggle("fonts-plain", settings?.useRetroFonts === false);
  document.body.style.setProperty("--content-font-scale", String(normalizeFontScale(settings?.fontScale)));
}

function updateFontScaleValue(value) {
  fontScaleValueEl.textContent = formatFontScale(value);
}

function formatFontScale(value) {
  return `${Math.round(normalizeFontScale(value) * 100)}%`;
}

function normalizeFontScale(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 1;
  }
  return Math.min(1.4, Math.max(0.85, Math.round(numeric * 100) / 100));
}
