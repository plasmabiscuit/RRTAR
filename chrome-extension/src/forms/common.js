(function registerAutofillCommon() {
  const FORM_DEFINITIONS = [
    { formType: "keyperson", iframePattern: "RR_KeyPersonExpanded_4_0", label: "R&R Senior/Key Person" },
    { formType: "budget", iframePattern: "RR_Budget_3_0", label: "R&R Budget" },
    { formType: "performance-site", iframePattern: "PerformanceSite_4_0", label: "Project/Performance Site" },
  ];

  const US_STATE_MAP = {
    AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas",
    CA: "California", CO: "Colorado", CT: "Connecticut", DE: "Delaware",
    FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho",
    IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas",
    KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland",
    MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi",
    MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada",
    NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York",
    NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma",
    OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina",
    SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah",
    VT: "Vermont", VA: "Virginia", WA: "Washington", WV: "West Virginia",
    WI: "Wisconsin", WY: "Wyoming", DC: "District of Columbia",
    AS: "American Samoa", GU: "Guam", MP: "Northern Mariana Islands",
    PR: "Puerto Rico", VI: "U.S. Virgin Islands",
  };
  const US_STATE_NAME_TO_ABBR = Object.fromEntries(
    Object.entries(US_STATE_MAP).map(([abbr, name]) => [name.toUpperCase(), abbr]),
  );

  function getFormDefinitionByType(formType) {
    return FORM_DEFINITIONS.find((item) => item.formType === formType) || null;
  }

  function getFormDefinitionByUrl(url) {
    const text = String(url || "");
    return FORM_DEFINITIONS.find((item) => text.includes(item.iframePattern)) || null;
  }

  function detectCurrentFrameForm() {
    const match = getFormDefinitionByUrl(window.location.href);
    if (!match) {
      return { supported: false, formType: null, iframeSrc: null, label: null };
    }
    return {
      supported: true,
      formType: match.formType,
      iframeSrc: window.location.href,
      label: match.label,
    };
  }

  function detectDocumentForm() {
    const selfDetection = detectCurrentFrameForm();
    if (selfDetection.supported) {
      return selfDetection;
    }
    const frames = Array.from(document.querySelectorAll("iframe"));
    for (const frame of frames) {
      const src = frame.getAttribute("src") || "";
      const match = getFormDefinitionByUrl(src);
      if (match) {
        return {
          supported: true,
          formType: match.formType,
          iframeSrc: src,
          label: match.label,
        };
      }
    }
    return { supported: false, formType: null, iframeSrc: null, label: null };
  }

  function findFormFrame(formType) {
    const def = getFormDefinitionByType(formType);
    if (!def) {
      return null;
    }
    const frames = Array.from(document.querySelectorAll("iframe"));
    return frames.find((frame) => {
      const src = frame.getAttribute("src") || "";
      return src.includes(def.iframePattern);
    }) || null;
  }

  function normalizeChoice(value) {
    return String(value || "")
      .toUpperCase()
      .trim()
      .replace(/[^A-Z0-9]/g, "");
  }

  function dispatchInputEvents(element) {
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    element.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  function getElement(doc, selectorOrId) {
    if (!selectorOrId) {
      return null;
    }
    if (selectorOrId.startsWith("#") || selectorOrId.includes("[") || selectorOrId.includes(" ") || selectorOrId.includes(".")) {
      return doc.querySelector(selectorOrId);
    }
    return doc.getElementById(selectorOrId);
  }

  function setControlValue(doc, selectorOrId, value, options = {}) {
    const element = getElement(doc, selectorOrId);
    if (!element) {
      return { ok: false, error: `Field not found: ${selectorOrId}` };
    }

    const normalizedValue = value == null ? "" : String(value);
    if (!options.allowEmpty && normalizedValue === "") {
      return { ok: true, skipped: true };
    }

    const tag = element.tagName;
    if (tag === "SELECT") {
      return selectControlValue(doc, selectorOrId, normalizedValue, options);
    }

    if (element.type === "checkbox" || element.type === "radio") {
      const shouldCheck = normalizedValue === "true" || normalizedValue === "1" || normalizedValue === "yes";
      if (element.checked !== shouldCheck) {
        element.click();
      }
      return { ok: true, value: shouldCheck };
    }

    element.focus();
    element.value = normalizedValue;
    dispatchInputEvents(element);
    return { ok: true, value: normalizedValue };
  }

  function selectControlValue(doc, selectorOrId, value, options = {}) {
    const element = getElement(doc, selectorOrId);
    if (!element) {
      return { ok: false, error: `Select not found: ${selectorOrId}` };
    }
    const rawValue = value == null ? "" : String(value);
    const candidates = [rawValue];
    if (options.treatAsState) {
      const upper = rawValue.toUpperCase().trim();
      if (US_STATE_MAP[upper]) {
        candidates.push(US_STATE_MAP[upper]);
      } else if (US_STATE_NAME_TO_ABBR[upper]) {
        candidates.push(US_STATE_NAME_TO_ABBR[upper]);
      }
    }

    const normalizedCandidates = new Set(candidates.map(normalizeChoice).filter(Boolean));
    let matchedOption = null;

    for (const option of Array.from(element.options || [])) {
      const label = option.textContent || "";
      const optValue = option.value || "";
      if (
        normalizedCandidates.has(normalizeChoice(label)) ||
        normalizedCandidates.has(normalizeChoice(optValue))
      ) {
        matchedOption = option;
        break;
      }
    }

    if (!matchedOption && rawValue === "") {
      matchedOption = Array.from(element.options || []).find((option) => !String(option.value || "").trim()) || null;
    }
    if (!matchedOption) {
      return { ok: false, error: `No matching option for ${selectorOrId}: ${rawValue}` };
    }

    element.value = matchedOption.value;
    dispatchInputEvents(element);
    return { ok: true, value: matchedOption.value };
  }

  function setCheckboxValue(doc, selectorOrId, checked) {
    const element = getElement(doc, selectorOrId);
    if (!element) {
      return { ok: false, error: `Checkbox not found: ${selectorOrId}` };
    }
    const next = Boolean(checked);
    if (Boolean(element.checked) !== next) {
      element.click();
    }
    return { ok: true, value: next };
  }

  function countExisting(doc, selectorTemplate, maxCount, start = 1) {
    let count = 0;
    for (let idx = start; idx <= maxCount; idx += 1) {
      const selector = selectorTemplate.replace("{N}", String(idx));
      if (doc.querySelector(selector)) {
        count = idx;
      }
    }
    return count;
  }

  function clickFirstButtonByText(doc, snippets) {
    for (const button of Array.from(doc.querySelectorAll("button"))) {
      const text = (button.textContent || "").trim();
      if (snippets.some((snippet) => text.includes(snippet))) {
        triggerButtonClick(button);
        return true;
      }
    }
    return false;
  }

  function isButtonEnabled(button) {
    if (!button) {
      return false;
    }
    return !button.disabled && !button.hasAttribute("disabled");
  }

  function triggerButtonClick(button) {
    if (!button) {
      return false;
    }
    button.focus();
    for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
      button.dispatchEvent(new MouseEvent(type, {
        bubbles: true,
        cancelable: true,
        view: window,
      }));
    }
    if (isButtonEnabled(button)) {
      button.click();
    }
    return true;
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  async function waitFor(check, timeoutMs = 5000, intervalMs = 100) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const result = check();
      if (result) {
        return result;
      }
      await sleep(intervalMs);
    }
    throw new Error(`Timed out after ${timeoutMs}ms`);
  }

  async function uploadAttachmentFromJob(doc, selectorOrId, path) {
    if (!path) {
      return { ok: true, skipped: true };
    }
    const input = getElement(doc, selectorOrId);
    if (!input) {
      return { ok: false, error: `Attachment input not found: ${selectorOrId}` };
    }
    const response = await chrome.runtime.sendMessage({
      type: "rrtar:fetch-attachment",
      path,
    });
    if (!response?.ok) {
      return { ok: false, error: response?.error || `Attachment fetch failed for ${path}` };
    }

    const bytes = base64ToUint8Array(response.base64 || "");
    const file = new File([bytes], response.fileName || basename(path), {
      type: response.mimeType || "application/pdf",
      lastModified: Date.now(),
    });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    dispatchInputEvents(input);
    return { ok: true, value: file.name };
  }

  function base64ToUint8Array(base64) {
    const clean = String(base64 || "");
    const binary = atob(clean);
    const bytes = new Uint8Array(binary.length);
    for (let idx = 0; idx < binary.length; idx += 1) {
      bytes[idx] = binary.charCodeAt(idx);
    }
    return bytes;
  }

  function basename(path) {
    const parts = String(path || "").split(/[\\/]/);
    return parts[parts.length - 1] || "attachment.pdf";
  }

  function accumulate(result, accumulator, kind, key) {
    if (result?.ok && !result.skipped) {
      accumulator[kind] += 1;
      return;
    }
    if (!result?.ok) {
      accumulator.errors.push(`${key}: ${result.error}`);
      return;
    }
  }

  function manifestWarnings(manifest) {
    const warnings = [];
    const entries = Array.isArray(manifest) ? manifest : [];
    for (const entry of entries) {
      const rowWarnings = entry?.validation?.warnings;
      if (Array.isArray(rowWarnings)) {
        warnings.push(...rowWarnings);
      }
    }
    return warnings;
  }

  self.RRTARAutofillCommon = {
    FORM_DEFINITIONS,
    accumulate,
    basename,
    clickFirstButtonByText,
    countExisting,
    detectCurrentFrameForm,
    detectDocumentForm,
    findFormFrame,
    getElement,
    getFormDefinitionByType,
    isButtonEnabled,
    manifestWarnings,
    selectControlValue,
    setCheckboxValue,
    setControlValue,
    sleep,
    triggerButtonClick,
    uploadAttachmentFromJob,
    waitFor,
  };
})();
