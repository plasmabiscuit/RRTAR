const DEFAULT_STATE = {
  activeTab: "keyperson",
  forms: {
    keyperson: { manifest: [] },
    budget: { manifest: [] },
    "performance-site": { manifest: [] },
  },
};

const STATE_KEY = "rrtar-dashboard-state-v1";
const SETTINGS_KEY = "rrtar-settings-v1";
const DB_NAME = "rrtar-dashboard-files";
const DB_VERSION = 1;
const STORE_FILES = "files";
const CONTACTS_DATA_URL = chrome.runtime.getURL("assets/data/contacts.json");
const CONTACT_SEARCH_LIMIT = 24;
const BACKEND_POLL_MS = 2000;
const BACKEND_TIMEOUT_MS = 120000;

const DEFAULT_SETTINGS = {
  backendBaseUrl: "https://150.230.162.179.sslip.io",
  apiKey: "",
  agency: "default",
  useRetroFonts: true,
};

let contactsCache = null;

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get([STATE_KEY, SETTINGS_KEY]);
  if (!current[STATE_KEY]) {
    await chrome.storage.local.set({ [STATE_KEY]: DEFAULT_STATE });
  }
  if (!current[SETTINGS_KEY]) {
    await chrome.storage.local.set({ [SETTINGS_KEY]: DEFAULT_SETTINGS });
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") {
    sendResponse({ ok: false, error: "Invalid message." });
    return false;
  }

  const handlers = {
    "rrtar:get-dashboard-state": () => getDashboardState(message.formType),
    "rrtar:set-dashboard-tab": () => setDashboardTab(message.tab),
    "rrtar:save-manifest": () => saveManifest(message.formType, message.manifest),
    "rrtar:clear-manifest": () => clearManifest(message.formType),
    "rrtar:list-files": () => listFiles(message.formType),
    "rrtar:put-file": () => putFile(message.formType, message.role, message.file, message.meta || {}),
    "rrtar:remove-file": () => removeFile(message.id),
    "rrtar:prepare-autofill": () => prepareAutofill(message.formType),
    "rrtar:fetch-attachment": () => fetchAttachment(message.path),
    "rrtar:open-dashboard": () => openDashboard(message.formType),
    "rrtar:search-contacts": () => searchContacts(message.query, message.limit),
    "rrtar:get-settings": () => getSettings(),
    "rrtar:set-settings": () => setSettings(message.settings),
    "rrtar:test-backend": () => testBackend(),
    "rrtar:run-backend-pipeline": () => runBackendPipeline(message.formType),
  };

  const handler = handlers[message.type];
  if (!handler) {
    sendResponse({ ok: false, error: `Unhandled message type: ${message.type}` });
    return false;
  }

  Promise.resolve()
    .then(handler)
    .then(sendResponse)
    .catch((error) => sendResponse({ ok: false, error: String(error) }));
  return true;
});

async function getDashboardState(formType) {
  const state = await readState();
  const settings = await readSettings();
  if (!formType) {
    return { ok: true, state, settings };
  }
  const files = await listFilesForForm(formType);
  return {
    ok: true,
    formType,
    activeTab: state.activeTab,
    manifest: state.forms?.[formType]?.manifest || [],
    backend: state.forms?.[formType]?.backend || null,
    files,
    preview: buildPreview(formType, state.forms?.[formType]?.manifest || []),
    settings,
  };
}

async function setDashboardTab(tab) {
  const state = await readState();
  state.activeTab = normalizeFormType(tab);
  await writeState(state);
  return { ok: true, activeTab: state.activeTab };
}

async function saveManifest(formType, manifest) {
  const cleanFormType = normalizeFormType(formType);
  const state = await readState();
  state.forms[cleanFormType] = {
    manifest: Array.isArray(manifest) ? manifest : [],
    backend: state.forms?.[cleanFormType]?.backend || null,
  };
  state.activeTab = cleanFormType;
  await writeState(state);
  return {
    ok: true,
    formType: cleanFormType,
    manifest: state.forms[cleanFormType].manifest,
    preview: buildPreview(cleanFormType, state.forms[cleanFormType].manifest),
  };
}

async function clearManifest(formType) {
  return saveManifest(formType, []);
}

async function listFiles(formType) {
  return {
    ok: true,
    formType: normalizeFormType(formType),
    files: await listFilesForForm(formType),
  };
}

async function putFile(formType, role, file, meta) {
  const cleanFormType = normalizeFormType(formType);
  const blob = normalizeUploadBlob(file, meta);
  if (!blob) {
    return { ok: false, error: "A file upload is required." };
  }

  const record = {
    id: crypto.randomUUID(),
    formType: cleanFormType,
    role: String(role || "attachment"),
    name: meta?.name || file?.name || "upload.pdf",
    mimeType: blob.type || meta?.mimeType || "application/octet-stream",
    size: Number(blob.size || meta?.size || 0),
    createdAt: new Date().toISOString(),
    blob,
  };
  await idbPut(record);
  return {
    ok: true,
    file: serializeFileRecord(record),
    path: `rrtar-file://${record.id}`,
  };
}

async function removeFile(id) {
  const cleanId = String(id || "").trim();
  if (!cleanId) {
    return { ok: false, error: "File id is required." };
  }
  await idbDelete(cleanId);
  return { ok: true };
}

async function prepareAutofill(formType) {
  const cleanFormType = normalizeFormType(formType);
  const state = await readState();
  let manifest = state.forms?.[cleanFormType]?.manifest || [];
  const backendJobId = state.forms?.[cleanFormType]?.backend?.jobId || "";
  const settings = await readSettings();
  manifest = await localizeManifestAttachments(cleanFormType, manifest, settings, backendJobId);
  state.forms[cleanFormType] = {
    manifest,
    backend: state.forms?.[cleanFormType]?.backend || null,
  };
  await writeState(state);
  return {
    ok: true,
    formType: cleanFormType,
    manifest,
    preview: buildPreview(cleanFormType, manifest),
  };
}

async function fetchAttachment(path) {
  const fileId = parsePseudoFilePath(path);
  if (fileId) {
    const record = await idbGet(fileId);
    if (!record?.blob) {
      return { ok: false, error: "Attachment file not found." };
    }
    const bytes = new Uint8Array(await record.blob.arrayBuffer());
    return {
      ok: true,
      fileName: record.name || "attachment.pdf",
      mimeType: record.mimeType || "application/octet-stream",
      base64: uint8ArrayToBase64(bytes),
    };
  }

  return fetchBackendArtifactAttachment(path);
}

async function openDashboard(formType) {
  const cleanFormType = normalizeFormType(formType);
  const url = chrome.runtime.getURL(`src/dashboard.html?tab=${encodeURIComponent(cleanFormType)}`);
  await chrome.tabs.create({ url });
  return { ok: true };
}

async function getSettings() {
  return { ok: true, settings: await readSettings() };
}

async function setSettings(settings) {
  const merged = mergeSettings(settings);
  await chrome.storage.local.set({ [SETTINGS_KEY]: merged });
  return { ok: true, settings: merged };
}

async function testBackend() {
  const settings = await readSettings();
  const baseUrl = requireBackendBaseUrl(settings);
  const health = await authorizedFetchJson(settings, `${baseUrl}/health`, { requireApiKey: false });
  const reference = await authorizedFetchJson(settings, `${baseUrl}/api/config/reference`);
  return {
    ok: true,
    health,
    reference,
    settings: {
      backendBaseUrl: settings.backendBaseUrl,
      agency: settings.agency,
      apiKeyPresent: Boolean(settings.apiKey),
    },
  };
}

async function runBackendPipeline(formType) {
  const cleanFormType = normalizeFormType(formType);
  const settings = await readSettings();
  const baseUrl = requireBackendBaseUrl(settings);
  if (!settings.apiKey.trim()) {
    throw new Error("API key is not configured. Open extension settings first.");
  }

  const sourceFiles = await listFileRecordsForForm(cleanFormType, "source-pdf");
  if (!sourceFiles.length) {
    throw new Error("No source PDFs are staged for this tab.");
  }
  const supplementalFiles = cleanFormType === "budget"
    ? await listFileRecordsForForm(cleanFormType, "budget-metadata")
    : [];

  const endpoint = getBackendJobEndpoint(cleanFormType);
  const formData = new FormData();
  for (const record of sourceFiles) {
    formData.append("files", new File([record.blob], record.name || "upload.pdf", {
      type: record.mimeType || "application/pdf",
      lastModified: Date.now(),
    }));
  }
  for (const record of supplementalFiles) {
    formData.append("files", new File([record.blob], record.name || "upload.budget.json", {
      type: record.mimeType || "application/json",
      lastModified: Date.now(),
    }));
  }
  if (cleanFormType === "keyperson") {
    formData.append("agency", settings.agency);
  }

  const createResponse = await fetch(`${baseUrl}${endpoint}`, {
    method: "POST",
    headers: {
      "x-api-key": settings.apiKey,
    },
    body: formData,
  });
  const job = await parseJsonResponse(createResponse, "Could not create backend job.");
  if (!createResponse.ok) {
    throw new Error(job?.detail || job?.error || "Backend job creation failed.");
  }

  const finalJob = await pollBackendJob(settings, baseUrl, job.id);
  if (finalJob.status !== "completed") {
    throw new Error(finalJob.error_text || `Backend job ended with status ${finalJob.status}.`);
  }

  const manifest = await authorizedFetchJson(settings, `${baseUrl}/api/jobs/${job.id}/manifest`);
  const localizedManifest = await localizeManifestAttachments(
    cleanFormType,
    Array.isArray(manifest) ? manifest : [],
    settings,
    job.id,
  );
  let validation = null;
  try {
    validation = await authorizedFetchJson(settings, `${baseUrl}/api/jobs/${job.id}/validation`);
  } catch {
    validation = null;
  }

  const state = await readState();
  state.forms[cleanFormType] = {
    manifest: localizedManifest,
    backend: {
      jobId: job.id,
      status: finalJob.status,
      jobType: finalJob.job_type,
      completedAt: finalJob.completed_at || null,
      result: finalJob.result || null,
      validation,
    },
  };
  state.activeTab = cleanFormType;
  await writeState(state);

  return {
    ok: true,
    formType: cleanFormType,
    job: finalJob,
    manifest: state.forms[cleanFormType].manifest,
    backend: state.forms[cleanFormType].backend,
    preview: buildPreview(cleanFormType, state.forms[cleanFormType].manifest),
  };
}

async function searchContacts(query, limit) {
  const contacts = await loadContacts();
  const normalizedQuery = String(query || "").trim();
  const maxResults = Math.max(1, Math.min(Number(limit) || CONTACT_SEARCH_LIMIT, 50));
  const results = rankContacts(contacts, normalizedQuery).slice(0, maxResults).map((contact, index) => ({
    id: contact.email || `${contact.fullName || "contact"}-${index}`,
    label: contact.fullName || [contact.firstName, contact.lastName].filter(Boolean).join(" ").trim() || contact.email || "Unknown contact",
    email: contact.email || "",
    jobTitle: contact.jobTitle || "",
    department: contact.department || "",
    unit: contact.unit || "",
    division: contact.Parent || "",
    workPhone: contact.workPhone || "",
    workLocation: contact.workLocation || "",
    campusBox: contact.campusBox || "",
    manifestEntry: buildKeyPersonEntryFromContact(contact),
  }));
  return {
    ok: true,
    query: normalizedQuery,
    total: results.length,
    results,
  };
}

async function readState() {
  const raw = await chrome.storage.local.get(STATE_KEY);
  return mergeState(raw[STATE_KEY] || {});
}

async function writeState(state) {
  await chrome.storage.local.set({ [STATE_KEY]: mergeState(state) });
}

async function readSettings() {
  const raw = await chrome.storage.local.get(SETTINGS_KEY);
  return mergeSettings(raw[SETTINGS_KEY] || {});
}

async function fetchBackendArtifactAttachment(path) {
  const cleanPath = String(path || "").trim();
  if (!cleanPath) {
    return { ok: false, error: "Attachment path is required." };
  }

  const settings = await readSettings();
  const baseUrl = settings.backendBaseUrl.trim();
  if (!baseUrl) {
    return { ok: false, error: "Attachment reference is not a clientside file id, and backend base URL is not configured." };
  }

  const state = await readState();
  const candidateJobIds = Object.values(state.forms || {})
    .map((formState) => formState?.backend?.jobId || "")
    .filter(Boolean);

  for (const jobId of candidateJobIds) {
    const response = await fetch(
      `${baseUrl}/api/jobs/${encodeURIComponent(jobId)}/artifacts/file?path=${encodeURIComponent(cleanPath)}`,
      {
        method: "GET",
        headers: settings.apiKey.trim() ? { "x-api-key": settings.apiKey } : {},
      },
    );
    if (!response.ok) {
      continue;
    }
    const blob = await response.blob();
    const bytes = new Uint8Array(await blob.arrayBuffer());
    return {
      ok: true,
      fileName: basename(cleanPath),
      mimeType: blob.type || "application/octet-stream",
      base64: uint8ArrayToBase64(bytes),
    };
  }

  return { ok: false, error: `Attachment file not found for path: ${cleanPath}` };
}

async function localizeManifestAttachments(formType, manifest, settings, jobId) {
  const localized = structuredClone(Array.isArray(manifest) ? manifest : []);
  if (!localized.length) {
    return localized;
  }
  const stagedFiles = await listFileRecordsForForm(formType);

  if (formType === "keyperson") {
    for (const entry of localized) {
      await localizeAttachmentPath(entry?.attachments?.biosketch, formType, "biosketch", settings, jobId, stagedFiles);
      await localizeAttachmentPath(entry?.attachments?.current_pending_support, formType, "current_pending_support", settings, jobId, stagedFiles);
    }
    return localized;
  }

  if (formType === "budget") {
    for (const entry of localized) {
      await localizeAttachmentPath(entry?.budget_justification, formType, "budget_justification", settings, jobId, stagedFiles);
      const periods = Array.isArray(entry?.periods) ? entry.periods : [];
      for (const period of periods) {
        const periodIndex = String(period?.period_index || "");
        const periodAttachments = entry?.period_attachments?.[periodIndex];
        if (periodAttachments && typeof periodAttachments === "object") {
          for (const [kind, pathValue] of Object.entries(periodAttachments)) {
            if (!pathValue) continue;
            periodAttachments[kind] = await resolveAttachmentPath(
              String(pathValue),
              formType,
              kind,
              settings,
              jobId,
              stagedFiles,
            );
          }
        }
        const inlineAttachments = period?.attachments;
        if (inlineAttachments && typeof inlineAttachments === "object") {
          for (const [kind, pathValue] of Object.entries(inlineAttachments)) {
            if (!pathValue) continue;
            inlineAttachments[kind] = await resolveAttachmentPath(
              String(pathValue),
              formType,
              kind,
              settings,
              jobId,
              stagedFiles,
            );
          }
        }
      }
    }
    return localized;
  }

  if (formType === "performance-site") {
    for (const entry of localized) {
      await localizeAttachmentPath(entry?.additional_sites_attachment, formType, "additional_sites_attachment", settings, jobId, stagedFiles);
    }
  }

  return localized;
}

async function localizeAttachmentPath(target, formType, role, settings, jobId, stagedFiles) {
  const originalPath = String(target?.path || "").trim();
  if (!target || !originalPath) {
    return;
  }
  target.path = await resolveAttachmentPath(originalPath, formType, role, settings, jobId, stagedFiles);
}

async function resolveAttachmentPath(path, formType, role, settings, jobId, stagedFiles) {
  const originalPath = String(path || "").trim();
  if (!originalPath || parsePseudoFilePath(originalPath)) {
    return originalPath;
  }
  const stagedMatch = matchStagedFileByPath(stagedFiles, originalPath, role);
  if (stagedMatch) {
    return `rrtar-file://${stagedMatch.id}`;
  }
  if (!jobId) {
    return originalPath;
  }
  try {
    return await persistBackendArtifactAsLocalFile(formType, role, originalPath, settings, jobId);
  } catch {
    return originalPath;
  }
}

function matchStagedFileByPath(stagedFiles, path, role) {
  const fileName = basename(path).toLowerCase();
  const preferredRole = String(role || "").toLowerCase();
  const matches = (Array.isArray(stagedFiles) ? stagedFiles : []).filter((record) => (
    String(record?.name || "").toLowerCase() === fileName
  ));
  if (!matches.length) {
    return null;
  }
  const roleMatch = matches.find((record) => String(record?.role || "").toLowerCase() === preferredRole);
  if (roleMatch) {
    return roleMatch;
  }
  const sourcePdfMatch = matches.find((record) => record.role === "source-pdf");
  return sourcePdfMatch || matches[0];
}

async function persistBackendArtifactAsLocalFile(formType, role, path, settings, jobId) {
  const response = await fetch(
    `${settings.backendBaseUrl}/api/jobs/${encodeURIComponent(jobId)}/artifacts/file?path=${encodeURIComponent(path)}`,
    {
      method: "GET",
      headers: settings.apiKey.trim() ? { "x-api-key": settings.apiKey } : {},
    },
  );
  if (!response.ok) {
    throw new Error(`Could not fetch backend artifact: ${path}`);
  }

  const blob = await response.blob();
  const record = {
    id: crypto.randomUUID(),
    formType: normalizeFormType(formType),
    role: String(role || "attachment"),
    name: basename(path),
    mimeType: blob.type || "application/octet-stream",
    size: Number(blob.size || 0),
    createdAt: new Date().toISOString(),
    blob,
  };
  await idbPut(record);
  return `rrtar-file://${record.id}`;
}

function mergeState(state) {
  const merged = JSON.parse(JSON.stringify(DEFAULT_STATE));
  if (state && typeof state === "object") {
    merged.activeTab = normalizeFormType(state.activeTab || merged.activeTab);
    for (const formType of Object.keys(merged.forms)) {
      if (Array.isArray(state.forms?.[formType]?.manifest)) {
        merged.forms[formType].manifest = state.forms[formType].manifest;
      }
      if (state.forms?.[formType]?.backend && typeof state.forms[formType].backend === "object") {
        merged.forms[formType].backend = state.forms[formType].backend;
      }
    }
  }
  return merged;
}

function mergeSettings(settings) {
  const merged = { ...DEFAULT_SETTINGS };
  if (settings && typeof settings === "object") {
    merged.backendBaseUrl = normalizeBackendBaseUrl(settings.backendBaseUrl || merged.backendBaseUrl);
    merged.apiKey = String(settings.apiKey || merged.apiKey).trim();
    merged.agency = String(settings.agency || merged.agency).trim() || "default";
    if (Object.prototype.hasOwnProperty.call(settings, "useRetroFonts")) {
      merged.useRetroFonts = Boolean(settings.useRetroFonts);
    }
  }
  return merged;
}

async function loadContacts() {
  if (contactsCache) {
    return contactsCache;
  }
  const response = await fetch(CONTACTS_DATA_URL);
  if (!response.ok) {
    throw new Error(`Could not load bundled contacts.json (${response.status}).`);
  }
  const raw = await response.json();
  const entries = Object.values(raw || {}).filter((item) => item && typeof item === "object");
  contactsCache = entries.sort((left, right) => {
    const a = `${left.lastName || ""}\u0000${left.firstName || ""}\u0000${left.email || ""}`.toLowerCase();
    const b = `${right.lastName || ""}\u0000${right.firstName || ""}\u0000${right.email || ""}`.toLowerCase();
    return a.localeCompare(b);
  });
  return contactsCache;
}

function getBackendJobEndpoint(formType) {
  if (formType === "budget") return "/api/jobs/budget";
  if (formType === "performance-site") return "/api/jobs/performance-site";
  return "/api/jobs/keyperson";
}

function requireBackendBaseUrl(settings) {
  const baseUrl = normalizeBackendBaseUrl(settings.backendBaseUrl);
  if (!baseUrl) {
    throw new Error("Backend base URL is not configured. Open extension settings first.");
  }
  return baseUrl;
}

function normalizeBackendBaseUrl(value) {
  const text = String(value || "").trim();
  return text.replace(/\/+$/, "");
}

async function pollBackendJob(settings, baseUrl, jobId) {
  const started = Date.now();
  while (Date.now() - started < BACKEND_TIMEOUT_MS) {
    const job = await authorizedFetchJson(settings, `${baseUrl}/api/jobs/${jobId}`);
    if (job?.status === "completed" || job?.status === "failed") {
      return job;
    }
    await sleep(BACKEND_POLL_MS);
  }
  throw new Error(`Timed out waiting for backend job ${jobId}.`);
}

async function authorizedFetchJson(settings, url, options = {}) {
  const requireApiKey = options.requireApiKey !== false;
  const headers = new Headers(options.headers || {});
  if (requireApiKey) {
    if (!settings.apiKey.trim()) {
      throw new Error("API key is not configured.");
    }
    headers.set("x-api-key", settings.apiKey);
  }
  const response = await fetch(url, {
    method: options.method || "GET",
    headers,
    body: options.body,
  });
  const payload = await parseJsonResponse(response, `Request failed: ${url}`);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.error || `${response.status} ${response.statusText}`);
  }
  return payload;
}

async function parseJsonResponse(response, fallbackMessage) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(fallbackMessage || text);
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function rankContacts(contacts, query) {
  if (!query) {
    return contacts;
  }
  const needle = query.toLowerCase().trim();
  const tokens = needle.split(/\s+/).filter(Boolean);
  return contacts
    .map((contact) => ({
      contact,
      score: scoreContact(contact, needle, tokens),
    }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || compareContacts(left.contact, right.contact))
    .map((item) => item.contact);
}

function scoreContact(contact, needle, tokens) {
  const fullName = String(contact.fullName || [contact.firstName, contact.lastName].filter(Boolean).join(" ")).trim();
  const email = String(contact.email || "");
  const haystacks = [
    fullName,
    email,
    contact.department,
    contact.unit,
    contact.Parent,
    contact.jobTitle,
    contact.workLocation,
    contact.campusBox,
  ].map((value) => String(value || "").toLowerCase());

  let score = 0;
  if (fullName.toLowerCase() === needle) score += 140;
  if (email.toLowerCase() === needle) score += 140;
  if (fullName.toLowerCase().startsWith(needle)) score += 110;
  if (email.toLowerCase().startsWith(needle)) score += 110;
  if (haystacks.some((value) => value.includes(needle))) score += 50;
  for (const token of tokens) {
    if (haystacks.some((value) => value.includes(token))) {
      score += 18;
    } else {
      score -= 12;
    }
  }
  return score;
}

function compareContacts(left, right) {
  return `${left.lastName || ""}\u0000${left.firstName || ""}\u0000${left.email || ""}`
    .localeCompare(`${right.lastName || ""}\u0000${right.firstName || ""}\u0000${right.email || ""}`);
}

function buildKeyPersonEntryFromContact(contact) {
  const street2 = formatCampusBox(contact.campusBox);
  return {
    source_pdf: "contacts.json",
    source_element: "ContactDirectory",
    source_index: 0,
    target_action: "add_as_key_person",
    exclude: false,
    person: {
      prefix: "",
      first_name: contact.firstName || "",
      middle_name: "",
      last_name: contact.lastName || "",
      suffix: "",
      title: contact.jobTitle || "",
      organization_name: inferOrganizationName(contact),
      department: contact.department || "",
      division: contact.Parent || "",
      credential: "",
      project_role: "",
      other_project_role_category: "",
      degree_type: "",
      degree_year: "",
      address: {
        street1: street2 ? "1 William L. Jones Dr" : "",
        street2,
        city: "Cookeville",
        county: "Putnam",
        state: "TN: Tennessee",
        province: "",
        country: "",
        postal_code: "388505-0001",
      },
      phone: contact.workPhone || "",
      fax: "",
      email: contact.email || "",
    },
    attachments: {
      biosketch: {
        required: true,
        source: "contacts-directory",
        path: "",
        sha1_base64: null,
      },
      current_pending_support: {
        required: false,
        source: "contacts-directory",
        path: "",
        sha1_base64: null,
      },
    },
    validation: {
      schema_valid: true,
      business_rules_valid: false,
      warnings: [
        "Added from bundled contacts.json; review role, address, email, and attachments before automate.",
      ],
    },
  };
}

function inferOrganizationName(contact) {
  const email = String(contact.email || "").toLowerCase();
  if (email.endsWith("@tntech.edu")) {
    return "Tennessee Technological University";
  }
  return "";
}

function formatCampusBox(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  return /^campus box\b/i.test(text) ? text : `Campus Box ${text}`;
}

function basename(path) {
  const parts = String(path || "").split(/[\\/]/);
  return parts[parts.length - 1] || "";
}

function normalizeFormType(value) {
  const text = String(value || "").trim();
  if (text === "budget" || text === "performance-site") {
    return text;
  }
  return "keyperson";
}

function buildPreview(formType, manifest) {
  if (formType === "keyperson") {
    const entries = Array.isArray(manifest) ? manifest.filter((entry) => !entry?.exclude) : [];
    const warnings = entries.flatMap((entry) => entry?.validation?.warnings || []);
    return {
      title: "Key Person",
      lines: [
        `People included: ${entries.length}`,
        `Manifest entries: ${Array.isArray(manifest) ? manifest.length : 0}`,
        `Warnings: ${warnings.length}`,
      ],
      warnings,
    };
  }
  if (formType === "budget") {
    const entries = Array.isArray(manifest) ? manifest : [];
    const periods = entries.reduce((count, entry) => count + (Array.isArray(entry?.periods) ? entry.periods.length : 0), 0);
    return {
      title: "Budget",
      lines: [
        `Budget sources: ${entries.length}`,
        `Budget periods: ${periods}`,
      ],
      warnings: [],
    };
  }
  const entries = Array.isArray(manifest) ? manifest : [];
  const sites = entries.reduce((count, entry) => count + (entry?.primary_site ? 1 : 0) + (Array.isArray(entry?.other_sites) ? entry.other_sites.length : 0), 0);
  return {
    title: "Performance Site",
    lines: [
      `Manifest sources: ${entries.length}`,
      `Sites queued: ${sites}`,
    ],
    warnings: [],
  };
}

function parsePseudoFilePath(path) {
  const text = String(path || "").trim();
  const prefix = "rrtar-file://";
  return text.startsWith(prefix) ? text.slice(prefix.length) : "";
}

function serializeFileRecord(record) {
  return {
    id: record.id,
    formType: record.formType,
    role: record.role,
    name: record.name,
    mimeType: record.mimeType,
    size: record.size,
    createdAt: record.createdAt,
  };
}

function normalizeUploadBlob(file, meta) {
  if (file instanceof Blob) {
    return file;
  }
  const base64 = String(file?.base64 || "").trim();
  if (!base64) {
    return null;
  }
  const bytes = base64ToUint8Array(base64);
  return new Blob([bytes], {
    type: String(file?.mimeType || meta?.mimeType || "application/octet-stream"),
  });
}

async function listFilesForForm(formType) {
  const cleanFormType = normalizeFormType(formType);
  const files = await idbList(cleanFormType);
  return files.map(serializeFileRecord);
}

async function listFileRecordsForForm(formType, role = "") {
  const cleanFormType = normalizeFormType(formType);
  const files = await idbList(cleanFormType);
  return role ? files.filter((file) => file.role === role) : files;
}

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_FILES)) {
        const store = db.createObjectStore(STORE_FILES, { keyPath: "id" });
        store.createIndex("formType", "formType", { unique: false });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Could not open IndexedDB."));
  });
}

async function idbPut(record) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_FILES, "readwrite");
    tx.objectStore(STORE_FILES).put(record);
    tx.oncomplete = () => resolve(record);
    tx.onerror = () => reject(tx.error || new Error("Could not store file."));
  });
}

async function idbGet(id) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_FILES, "readonly");
    const request = tx.objectStore(STORE_FILES).get(id);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error || new Error("Could not read file."));
  });
}

async function idbDelete(id) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_FILES, "readwrite");
    tx.objectStore(STORE_FILES).delete(id);
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error || new Error("Could not delete file."));
  });
}

async function idbList(formType) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_FILES, "readonly");
    const request = tx.objectStore(STORE_FILES).getAll();
    request.onsuccess = () => {
      const rows = Array.isArray(request.result) ? request.result : [];
      resolve(rows.filter((row) => row.formType === formType));
    };
    request.onerror = () => reject(request.error || new Error("Could not list files."));
  });
}

function uint8ArrayToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let idx = 0; idx < bytes.length; idx += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(idx, idx + chunkSize));
  }
  return btoa(binary);
}

function base64ToUint8Array(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let idx = 0; idx < binary.length; idx += 1) {
    bytes[idx] = binary.charCodeAt(idx);
  }
  return bytes;
}
