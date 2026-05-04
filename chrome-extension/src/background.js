const DEFAULT_SETTINGS = {
  backendBaseUrl: "http://100.117.80.82:8081",
  sharedApiKey: "",
};

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  await chrome.storage.sync.set({
    backendBaseUrl: current.backendBaseUrl || DEFAULT_SETTINGS.backendBaseUrl,
    sharedApiKey: current.sharedApiKey || DEFAULT_SETTINGS.sharedApiKey,
  });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") {
    sendResponse({ ok: false, error: "Invalid message." });
    return false;
  }

  if (message.type === "rrtar:get-settings") {
    chrome.storage.sync.get(DEFAULT_SETTINGS).then((settings) => {
      sendResponse({ ok: true, settings });
    });
    return true;
  }

  if (message.type === "rrtar:set-settings") {
    chrome.storage.sync
      .set({
        backendBaseUrl: String(message.backendBaseUrl || DEFAULT_SETTINGS.backendBaseUrl).trim(),
        sharedApiKey: String(message.sharedApiKey || "").trim(),
      })
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "rrtar:fetch-manifest") {
    fetchManifest(message.jobId).then(sendResponse);
    return true;
  }

  sendResponse({ ok: false, error: `Unhandled message type: ${message.type}` });
  return false;
});

async function fetchManifest(jobId) {
  const cleanJobId = String(jobId || "").trim();
  if (!cleanJobId) {
    return { ok: false, error: "Job ID is required." };
  }

  const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  const baseUrl = String(settings.backendBaseUrl || DEFAULT_SETTINGS.backendBaseUrl).replace(/\/+$/, "");
  const apiKey = String(settings.sharedApiKey || "").trim();
  const headers = {};

  if (apiKey) {
    headers["x-api-key"] = apiKey;
  }

  try {
    const response = await fetch(`${baseUrl}/jobs/${encodeURIComponent(cleanJobId)}/manifest`, {
      method: "GET",
      headers,
    });

    const bodyText = await response.text();
    let body = null;
    try {
      body = bodyText ? JSON.parse(bodyText) : null;
    } catch {
      body = bodyText;
    }

    if (!response.ok) {
      return {
        ok: false,
        error: `Manifest fetch failed with ${response.status}.`,
        details: body,
      };
    }

    return { ok: true, manifest: body, backendBaseUrl: baseUrl };
  } catch (error) {
    return { ok: false, error: `Network error: ${String(error)}` };
  }
}
