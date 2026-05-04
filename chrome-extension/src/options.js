const backendInput = document.querySelector("#backend-base-url");
const apiKeyInput = document.querySelector("#shared-api-key");
const saveBtn = document.querySelector("#save-btn");
const statusEl = document.querySelector("#status");

loadSettings();

saveBtn.addEventListener("click", async () => {
  const backendBaseUrl = backendInput.value.trim();
  const sharedApiKey = apiKeyInput.value.trim();

  const result = await chrome.runtime.sendMessage({
    type: "rrtar:set-settings",
    backendBaseUrl,
    sharedApiKey,
  });

  statusEl.textContent = result?.ok ? "Settings saved." : result?.error || "Save failed.";
});

async function loadSettings() {
  const result = await chrome.runtime.sendMessage({ type: "rrtar:get-settings" });
  if (!result?.ok) {
    statusEl.textContent = result?.error || "Could not load settings.";
    return;
  }

  backendInput.value = result.settings.backendBaseUrl || "";
  apiKeyInput.value = result.settings.sharedApiKey || "";
}
