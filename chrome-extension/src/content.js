(function bootstrapContentScript() {
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || typeof message !== "object") {
      sendResponse({ ok: false, error: "Invalid message." });
      return false;
    }

    if (message.type === "rrtar:detect-form") {
      sendResponse({ ok: true, detection: detectCurrentForm() });
      return false;
    }

    if (message.type === "rrtar:autofill-manifest") {
      handleAutofill(message.manifest).then(sendResponse);
      return true;
    }

    sendResponse({ ok: false, error: `Unhandled content message type: ${message.type}` });
    return false;
  });
})();

function detectCurrentForm() {
  const frames = Array.from(document.querySelectorAll("iframe"));
  for (const frame of frames) {
    const src = frame.getAttribute("src") || "";
    if (src.includes("RR_KeyPersonExpanded_4_0")) {
      return { supported: true, formType: "keyperson", iframeSrc: src };
    }
    if (src.includes("RR_Budget_3_0")) {
      return { supported: true, formType: "budget", iframeSrc: src };
    }
    if (src.includes("PerformanceSite_4_0")) {
      return { supported: true, formType: "performance-site", iframeSrc: src };
    }
  }
  return { supported: false, formType: null, iframeSrc: null };
}

async function handleAutofill(manifest) {
  const detection = detectCurrentForm();
  if (!detection.supported) {
    return { ok: false, error: "No supported Grants.gov form iframe detected in the current tab." };
  }

  if (detection.formType === "keyperson") {
    return self.RRTARKeyPersonAutofill.run(manifest);
  }
  if (detection.formType === "budget") {
    return self.RRTARBudgetAutofill.run(manifest);
  }
  if (detection.formType === "performance-site") {
    return self.RRTARPerformanceSiteAutofill.run(manifest);
  }

  return { ok: false, error: `Unsupported form type: ${detection.formType}` };
}
