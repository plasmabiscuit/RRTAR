const DEFAULT_STATE = {
  activeTab: "keyperson",
  forms: {
    keyperson: { manifest: [] },
    budget: { manifest: [] },
    "performance-site": { manifest: [] },
  },
};

const STATE_KEY = "rrtar-dashboard-state-v1";
const DB_NAME = "rrtar-dashboard-files";
const DB_VERSION = 1;
const STORE_FILES = "files";

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get(STATE_KEY);
  if (!current[STATE_KEY]) {
    await chrome.storage.local.set({ [STATE_KEY]: DEFAULT_STATE });
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
    "rrtar:get-settings": async () => ({ ok: true, settings: {} }),
    "rrtar:set-settings": async () => ({ ok: true }),
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
  if (!formType) {
    return { ok: true, state };
  }
  const files = await listFilesForForm(formType);
  return {
    ok: true,
    formType,
    activeTab: state.activeTab,
    manifest: state.forms?.[formType]?.manifest || [],
    files,
    preview: buildPreview(formType, state.forms?.[formType]?.manifest || []),
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
  state.forms[cleanFormType] = { manifest: Array.isArray(manifest) ? manifest : [] };
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
  if (!(file instanceof Blob)) {
    return { ok: false, error: "A file upload is required." };
  }

  const record = {
    id: crypto.randomUUID(),
    formType: cleanFormType,
    role: String(role || "attachment"),
    name: meta?.name || file.name || "upload.pdf",
    mimeType: file.type || meta?.mimeType || "application/octet-stream",
    size: Number(file.size || meta?.size || 0),
    createdAt: new Date().toISOString(),
    blob: file,
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
  const manifest = state.forms?.[cleanFormType]?.manifest || [];
  return {
    ok: true,
    formType: cleanFormType,
    manifest,
    preview: buildPreview(cleanFormType, manifest),
  };
}

async function fetchAttachment(path) {
  const fileId = parsePseudoFilePath(path);
  if (!fileId) {
    return { ok: false, error: "Attachment reference is not a clientside file id." };
  }
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

async function openDashboard(formType) {
  const cleanFormType = normalizeFormType(formType);
  const url = chrome.runtime.getURL(`src/dashboard.html?tab=${encodeURIComponent(cleanFormType)}`);
  await chrome.tabs.create({ url });
  return { ok: true };
}

async function readState() {
  const raw = await chrome.storage.local.get(STATE_KEY);
  return mergeState(raw[STATE_KEY] || {});
}

async function writeState(state) {
  await chrome.storage.local.set({ [STATE_KEY]: mergeState(state) });
}

function mergeState(state) {
  const merged = JSON.parse(JSON.stringify(DEFAULT_STATE));
  if (state && typeof state === "object") {
    merged.activeTab = normalizeFormType(state.activeTab || merged.activeTab);
    for (const formType of Object.keys(merged.forms)) {
      if (Array.isArray(state.forms?.[formType]?.manifest)) {
        merged.forms[formType].manifest = state.forms[formType].manifest;
      }
    }
  }
  return merged;
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

async function listFilesForForm(formType) {
  const cleanFormType = normalizeFormType(formType);
  const files = await idbList(cleanFormType);
  return files.map(serializeFileRecord);
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
