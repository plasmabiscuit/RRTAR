(function bootstrapContentScript() {
  const common = self.RRTARAutofillCommon;
  const pendingAutofillRequests = new Map();

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || typeof message !== "object") {
      sendResponse({ ok: false, error: "Invalid message." });
      return false;
    }

    if (window !== window.top) {
      return false;
    }

    if (message.type === "rrtar:detect-form") {
      sendResponse({ ok: true, detection: detectCurrentForm() });
      return false;
    }

    if (message.type === "rrtar:autofill-manifest") {
      handleAutofill(message.payload).then(sendResponse);
      return true;
    }

    sendResponse({ ok: false, error: `Unhandled content message type: ${message.type}` });
    return false;
  });

  window.addEventListener("message", (event) => {
    const data = event.data;
    if (!data || data.source !== "rrtar-extension") {
      return;
    }

    if (data.type === "rrtar:iframe-autofill-result" && window === window.top) {
      const pending = pendingAutofillRequests.get(data.requestId);
      if (!pending) {
        return;
      }
      pendingAutofillRequests.delete(data.requestId);
      pending.resolve(data.result);
      return;
    }

    if (data.type === "rrtar:iframe-autofill-request" && window !== window.top) {
      const detection = common.detectCurrentFrameForm();
      if (!detection.supported) {
        return;
      }
      if (data.formType && detection.formType !== data.formType) {
        return;
      }
      runAutofillInCurrentFrame(data.payload)
        .then((result) => {
          window.top.postMessage({
            source: "rrtar-extension",
            type: "rrtar:iframe-autofill-result",
            requestId: data.requestId,
            result,
          }, "*");
        })
        .catch((error) => {
          window.top.postMessage({
            source: "rrtar-extension",
            type: "rrtar:iframe-autofill-result",
            requestId: data.requestId,
            result: {
              ok: false,
              error: error?.message || String(error),
              details: error?.stack ? { stack: String(error.stack) } : undefined,
            },
          }, "*");
        });
    }
  });

  function detectCurrentForm() {
    return common.detectDocumentForm();
  }

  async function handleAutofill(payload) {
    const detection = detectCurrentForm();
    if (!detection.supported) {
      return { ok: false, error: "No supported Grants.gov form iframe detected in the current tab." };
    }

    if (!payload || typeof payload !== "object") {
      return { ok: false, error: "Autofill payload is required." };
    }
    if (payload.formType && payload.formType !== detection.formType) {
      return {
        ok: false,
        error: `Manifest form ${payload.formType} does not match detected form ${detection.formType}.`,
        details: { formType: payload.formType, detectedFormType: detection.formType },
      };
    }

    if (window !== window.top) {
      return runAutofillInCurrentFrame(payload);
    }

    const targetFrame = common.findFormFrame(detection.formType);
    if (!targetFrame?.contentWindow) {
      return { ok: false, error: `Could not access iframe for ${detection.formType}.` };
    }

    const requestId = `rrtar-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const resultPromise = new Promise((resolve) => {
      const timeoutId = window.setTimeout(() => {
        pendingAutofillRequests.delete(requestId);
        resolve({ ok: false, error: "Timed out waiting for iframe autofill response." });
      }, 45000);
      pendingAutofillRequests.set(requestId, {
        resolve: (result) => {
          window.clearTimeout(timeoutId);
          resolve(result);
        },
      });
    });

    targetFrame.contentWindow.postMessage({
      source: "rrtar-extension",
      type: "rrtar:iframe-autofill-request",
      requestId,
      formType: detection.formType,
      payload,
    }, "*");

    return resultPromise;
  }

  async function runAutofillInCurrentFrame(payload) {
    const detection = common.detectCurrentFrameForm();
    if (!detection.supported) {
      return { ok: false, error: "Autofill target is not inside a supported Grants.gov form frame." };
    }

    if (detection.formType === "keyperson") {
      return self.RRTARKeyPersonAutofill.run(payload);
    }
    if (detection.formType === "budget") {
      return self.RRTARBudgetAutofill.run(payload);
    }
    if (detection.formType === "performance-site") {
      return self.RRTARPerformanceSiteAutofill.run(payload);
    }
    return { ok: false, error: `Unsupported form type: ${detection.formType}` };
  }
})();
