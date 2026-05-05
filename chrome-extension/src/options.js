const backendBaseUrlEl = document.querySelector("#backend-base-url");
const apiKeyEl = document.querySelector("#api-key");
const agencyEl = document.querySelector("#agency");
const saveSettingsBtn = document.querySelector("#save-settings-btn");
const testBackendBtn = document.querySelector("#test-backend-btn");
const openDashboardBtn = document.querySelector("#open-dashboard-btn");
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
}

saveSettingsBtn.addEventListener("click", async () => {
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:set-settings",
    settings: {
      backendBaseUrl: backendBaseUrlEl.value,
      apiKey: apiKeyEl.value,
      agency: agencyEl.value,
    },
  });
  statusEl.textContent = result?.ok
    ? `Saved backend settings for ${result.settings.backendBaseUrl || "no backend URL"}.`
    : result?.error || "Could not save settings.";
});

testBackendBtn.addEventListener("click", async () => {
  statusEl.textContent = "Testing backend...";
  const saveResult = await chrome.runtime.sendMessage({
    type: "rrtar:set-settings",
    settings: {
      backendBaseUrl: backendBaseUrlEl.value,
      apiKey: apiKeyEl.value,
      agency: agencyEl.value,
    },
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
