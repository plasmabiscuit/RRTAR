const ICONS = {
  addressbook: {
    sm: "../assets/icons/PNG/for-dark-mode/16px/regular/book-bookmark.png",
    lg: "../assets/icons/PNG/for-dark-mode/48px/regular/book-bookmark.png",
  },
  automate: {
    sm: "../assets/icons/PNG/for-light-mode/16px/solid/file-import.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/solid/file-import.png",
  },
  budget: {
    sm: "../assets/icons/PNG/for-light-mode/16px/solid/receipt.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/solid/receipt.png",
  },
  check: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/check.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/check.png",
  },
  close: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/times.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/times.png",
  },
  file: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/notebook.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/notebook.png",
  },
  folder: {
    sm: "../assets/icons/PNG/for-dark-mode/16px/solid/folder-open.png",
    lg: "../assets/icons/PNG/for-dark-mode/48px/solid/folder-open.png",
  },
  globe: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/globe.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/globe.png",
  },
  manifestchip: {
    sm: "../assets/img/manifest.png",
    lg: "../assets/img/manifest.png",
  },
  pause: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/pause.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/pause.png",
  },
  people: {
    sm: "../assets/icons/PNG/for-light-mode/16px/solid/user.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/solid/user.png",
  },
  pdfschip: {
    sm: "../assets/img/pdfs.png",
    lg: "../assets/img/pdfs.png",
  },
  pin: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/location-pin.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/location-pin.png",
  },
  pipelinechip: {
    sm: "../assets/img/pipeline.png",
    lg: "../assets/img/pipeline.png",
  },
  play: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/play.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/play.png",
  },
  save: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/save.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/save.png",
  },
  trash: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/trash.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/trash.png",
  },
  upload: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/upload-alt.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/upload-alt.png",
  },
  warning: {
    sm: "../assets/icons/PNG/for-light-mode/16px/regular/exclaimation.png",
    lg: "../assets/icons/PNG/for-light-mode/48px/regular/exclaimation.png",
  },
};

const TAB_DEFS = {
  keyperson: {
    title: "Key Person",
    pipelineTitle: "Pipeline",
    dropTitle: "Input PDFs",
    manifestTitle: "Import Manifest",
    tabIcon: "people",
    pipelineIcon: "pipelinechip",
    dropIcon: "pdfschip",
    manifestIcon: "manifestchip",
    uploadHint: "Drop Key Person PDFs here",
    automateStep: "automate",
    steps: [
      ["fetch-schemas", "Download and pin Grants.gov XSD schemas", false],
      ["extract", "Parse XFA XML and attachments from input PDFs", true],
      ["validate", "Schema and business-rule validation", true],
      ["normalize", "Build import_manifest.json for review", true],
      ["automate", "Drive the live Grants.gov form", true],
    ],
  },
  budget: {
    title: "Budget",
    pipelineTitle: "Budget Pipeline",
    dropTitle: "Budget PDFs",
    manifestTitle: "Budget Manifest",
    tabIcon: "budget",
    pipelineIcon: "pipelinechip",
    dropIcon: "pdfschip",
    manifestIcon: "manifestchip",
    uploadHint: "Drop Budget PDFs here",
    automateStep: "automate-budget",
    steps: [
      ["extract-budget", "Parse budget PDFs into reviewable data", true],
      ["normalize-budget", "Build budget_manifest.json for review", true],
      ["automate-budget", "Drive the live R&R Budget form", true],
    ],
  },
  "performance-site": {
    title: "Performance Site",
    pipelineTitle: "Performance Site Pipeline",
    dropTitle: "Performance Site PDFs",
    manifestTitle: "Performance Site Manifest",
    tabIcon: "pin",
    pipelineIcon: "pipelinechip",
    dropIcon: "pdfschip",
    manifestIcon: "manifestchip",
    uploadHint: "Drop Performance Site PDFs here",
    automateStep: "automate-performance-site",
    steps: [
      ["extract-performance-site", "Parse Performance Site PDFs into reviewable data", true],
      ["normalize-performance-site", "Build performance_site_manifest.json for review", true],
      ["automate-performance-site", "Drive the live Performance Site form", true],
    ],
  },
};

const KEYPERSON_ROLE_OPTIONS = [
  "",
  "PD/PI",
  "Co-PD/PI",
  "Faculty",
  "Post Doctoral",
  "Post Doctoral Associate",
  "Post Doctoral Scholar",
  "Other Professional",
  "Graduate Student",
  "Undergraduate Student",
  "Technician",
  "Consultant",
  "Co-Investigator",
  "Other (Specify)",
];

const tabBar = document.querySelector("#tab-bar");
const appMain = document.querySelector("#app-main");
const statusStrip = document.querySelector("#status-strip");
const openGrantsBtn = document.querySelector("#open-grants-btn");
const contactModal = document.querySelector("#contact-modal");
const contactSearchInput = document.querySelector("#contact-search-input");
const contactSearchResults = document.querySelector("#contact-search-results");
const contactSearchMeta = document.querySelector("#contact-search-meta");
const contactModalCloseBtn = document.querySelector("#contact-modal-close");
const contactModalCancelBtn = document.querySelector("#contact-modal-cancel");

let activeTab = normalizeFormType(new URL(location.href).searchParams.get("tab") || "keyperson");
let currentState = null;
let currentContactResults = [];
let statusHideTimer = 0;
const STATUS_TIMEOUT_MS = 5000;

init();

async function init() {
  openGrantsBtn.innerHTML = `${icon("globe", "icon-btn")}Open Grants.gov`;
  openGrantsBtn.addEventListener("click", () => chrome.tabs.create({ url: "https://apply07.grants.gov/" }));
  await chrome.runtime.sendMessage({ type: "rrtar:set-dashboard-tab", tab: activeTab });
  renderTabs();
  await refreshState();
}

async function refreshState() {
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:get-dashboard-state",
    formType: activeTab,
  });
  if (!result?.ok) {
    setStatus(result?.error || "Could not load dashboard state.", "err");
    return;
  }
  currentState = result;
  renderPage();
}

function renderTabs() {
  tabBar.innerHTML = "";
  for (const [formType, def] of Object.entries(TAB_DEFS)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `tab-btn ${formType === activeTab ? "active" : ""}`.trim();
    button.innerHTML = `${icon(def.tabIcon, "icon-btn")}${escapeHtml(def.title)}`;
    button.addEventListener("click", async () => {
      activeTab = formType;
      history.replaceState(null, "", `?tab=${encodeURIComponent(activeTab)}`);
      await chrome.runtime.sendMessage({ type: "rrtar:set-dashboard-tab", tab: activeTab });
      renderTabs();
      await refreshState();
    });
    tabBar.appendChild(button);
  }
}

function renderPage() {
  const def = TAB_DEFS[activeTab];
  const manifest = currentState?.manifest || [];
  const files = currentState?.files || [];
  const preview = currentState?.preview || { lines: [], warnings: [] };
  const backend = currentState?.backend || null;

  const content = `
    <div class="row2">
      <div class="card">
        <h2>${icon(def.pipelineIcon, "icon-chip")}${escapeHtml(def.pipelineTitle)}</h2>
        <ul class="steps">${renderSteps(def, manifest, files)}</ul>
        <div class="automate-row">${renderAutomateButton(manifest)}</div>
        <div class="chrome-box">
          <button id="open-grants-inline" class="btn-primary btn-panel" type="button">${icon("globe", "icon-btn")}Open Grants.gov</button>
          <span class="chrome-info">${escapeHtml(renderPipelineSummary(preview, backend))}</span>
        </div>
      </div>
      <div class="card">
        <h2>${icon(def.dropIcon, "icon-chip")}${escapeHtml(def.dropTitle)} &nbsp;<span class="badge ${files.length ? "ok" : "pend"}">${files.length} file${files.length === 1 ? "" : "s"}</span></h2>
        <label id="drop-zone" class="drop-zone">
          <input type="file" id="pdf-file-input" accept=".pdf" multiple>
          <div class="dz-icon">${icon("upload")}</div>
          <div class="drop-zone-copy">
            <p><strong>${escapeHtml(def.uploadHint)}</strong> or click to browse</p>
            <p style="font-size:.8rem">PDFs staged here will appear below for this tab.</p>
          </div>
        </label>
        ${renderFileTable(files)}
      </div>
    </div>
    <div class="card" style="margin-bottom:1.2rem">
      <h2>${icon(def.manifestIcon, "icon-chip")}${escapeHtml(def.manifestTitle)} ${renderManifestBadge(manifest, preview)}</h2>
      <form id="manifest-import-form" class="manifest-save-bar">
        <span class="manifest-save-actions">
          <label class="btn-primary btn-sm" style="cursor:pointer">
            ${icon("file", "icon-btn")}Import Manifest JSON
            <input id="manifest-file-input" type="file" accept=".json,application/json" style="display:none">
          </label>
          ${activeTab === "keyperson" ? `<button id="add-contact-btn" class="btn-primary btn-sm" type="button">${icon("addressbook", "icon-btn")}Add From Contacts</button>` : ""}
          <button id="export-manifest-btn" class="btn-success btn-sm" type="button">${icon("save", "icon-btn")}Export Manifest</button>
          <button id="clear-manifest-btn" class="btn-warn btn-sm" type="button">${icon("trash", "icon-btn")}Clear Manifest</button>
        </span>
        <span class="manifest-save-note">${activeTab === "keyperson" ? "Build locally from bundled contacts, import a manifest JSON, or run the backend pipeline. Review warnings and required attachments before automate." : "Use the backend pipeline to generate a manifest from staged PDFs, or import a current manifest JSON for local review."}</span>
      </form>
      <div class="manifest-wrap">${renderManifest(activeTab, manifest, preview)}</div>
    </div>
  `;

  appMain.innerHTML = content;
  bindPageInteractions();
}

function renderSteps(def, manifest, files) {
  return def.steps.map(([name, hint, enabled]) => {
    const done = stepDone(name, manifest, files);
    const badge = done
      ? `<span class="badge done step-badge step-state" aria-label="done">${icon("check", "icon-status")}</span>`
      : `<span class="badge pend step-badge step-state">${enabled ? "pending" : "not yet"}</span>`;
    const action = enabled
      ? `<span class="step-action"><button type="button" class="btn-run step-btn" data-step="${escapeAttr(name)}">${icon("play", "icon-btn")}Run</button></span>`
      : `<span class="step-action"><button type="button" class="btn-disabled step-btn" disabled>${icon("play", "icon-btn")}Run</button></span>`;
    const fullHint = enabled ? hint : `${hint} — not yet ported to clientside`;
    return `<li>${action}<strong class="step-name">${escapeHtml(name)}</strong>${badge}<span class="step-hint">${escapeHtml(fullHint)}</span></li>`;
  }).join("");
}

function renderAutomateButton(manifest) {
  if (!Array.isArray(manifest) || manifest.length === 0) {
    return `<button class="btn-disabled btn-panel" type="button" disabled title="Import a manifest first">${icon("automate", "icon-btn")}Automate</button>`;
  }
  return `<button id="automate-btn" class="btn-automate btn-panel" type="button">${icon("automate", "icon-btn")}Automate</button>`;
}

function renderPipelineSummary(preview, backend) {
  const lines = Array.isArray(preview?.lines) ? preview.lines : [];
  if (backend?.jobId) {
    const stamp = backend.completedAt ? new Date(backend.completedAt).toLocaleString() : "in progress";
    lines.push(`Backend: ${backend.status || "unknown"} (${stamp})`);
  }
  return lines.join(" · ") || "Stage PDFs, run the backend pipeline, then automate.";
}

function renderFileTable(files) {
  const sourceFiles = files.filter((file) => file.role === "source-pdf");
  if (!sourceFiles.length) {
    return '<div class="upload-list"><p class="empty-note upload-list-empty">No PDFs yet — drop some above.</p></div>';
  }
  const rows = sourceFiles.map((file) => {
    const remove = `<button type="button" class="btn-danger btn-sm" data-remove-file="${escapeAttr(file.id)}">${icon("close", "icon-btn")}Remove</button>`;
    return `<tr><td><strong style="font-size:.83rem">${escapeHtml(file.name)}</strong></td><td class="sub-dim">${formatSize(file.size)}</td><td><span class="badge ok">staged</span> <span class="sub-info">ready</span></td><td style="text-align:right">${remove}</td></tr>`;
  }).join("");
  return `<div class="upload-list"><div class="upload-list-head"><span class="upload-list-title">Staged PDFs</span><span class="sub-dim">${sourceFiles.length} file${sourceFiles.length === 1 ? "" : "s"}</span></div><table><thead><tr><th>File</th><th>Size</th><th>Status</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderManifestBadge(manifest, preview) {
  const count = Array.isArray(manifest) ? manifest.length : 0;
  const warnings = Array.isArray(preview?.warnings) ? preview.warnings.length : 0;
  const badgeClass = count ? (warnings ? "warn" : "ok") : "pend";
  const label = activeTab === "keyperson"
    ? `${manifest.filter((entry) => !entry?.exclude).length} person${manifest.filter((entry) => !entry?.exclude).length === 1 ? "" : "s"} included`
    : `${count} source${count === 1 ? "" : "s"}`;
  const warnBadge = warnings ? ` &nbsp;<span class="badge warn">${icon("warning", "icon-status")}${warnings} warning${warnings === 1 ? "" : "s"}</span>` : "";
  return `&nbsp;<span class="badge ${badgeClass}">${escapeHtml(label)}</span>${warnBadge}`;
}

function renderManifest(formType, manifest, preview) {
  if (!Array.isArray(manifest) || manifest.length === 0) {
    return `<p class="empty-note">No ${escapeHtml(TAB_DEFS[formType].manifestTitle.toLowerCase())} — import a manifest JSON file first.</p>`;
  }
  if (formType === "keyperson") {
    return renderKeypersonManifest(manifest, preview);
  }
  if (formType === "budget") {
    return renderBudgetManifest(manifest);
  }
  return renderPerformanceSiteManifest(manifest);
}

function renderKeypersonManifest(manifest, preview) {
  const rows = manifest.map((entry, index) => {
    const person = entry.person || {};
    const name = [person.prefix, person.first_name, person.middle_name, person.last_name, person.suffix].filter(Boolean).join(" ").trim() || "—";
    const sourcePdf = basename(entry.source_pdf || "");
    const srcLabel = entry.source_element === "ContactDirectory"
      ? "Address Book"
      : (entry.source_element === "AttachmentFallback" ? "Attachment" : `${entry.source_element || "PDPI"}${typeof entry.source_index === "number" ? `[${entry.source_index}]` : ""}`);
    const warnings = Array.isArray(entry?.validation?.warnings) ? entry.validation.warnings : [];
    const attach = entry.attachments || {};
    const bio = attach.biosketch?.path || "";
    const sup = attach.current_pending_support?.path || "";
    const roleValue = normalizeProjectRoleValue(person.project_role || "");
    const roleOptions = buildKeypersonRoleOptions(roleValue).map((role) => (
      `<option value="${escapeAttr(role)}"${role === roleValue ? " selected" : ""}>${escapeHtml(role || "— select role —")}</option>`
    )).join("");
    const showOtherRole = roleValue === "Other (Specify)";
    return `<tr>
      <td>${renderEntryActions(index, entry)}</td>
      <td><span class="person-name">${escapeHtml(name)}</span><br><span class="person-src">${escapeHtml(sourcePdf)} / ${escapeHtml(srcLabel)}</span></td>
      <td>${person.email ? `<a href="mailto:${escapeAttr(person.email)}" class="sub-info">${escapeHtml(person.email)}</a>` : '<span class="sub-dim">—</span>'}${person.phone ? `<br><span class="sub-dim">${escapeHtml(person.phone)}</span>` : ""}</td>
      <td>${escapeHtml(person.organization_name || "—")}${person.department || person.division ? `<div class="sub-dim" style="margin-top:.2rem">${escapeHtml([person.department || "", person.division || ""].filter(Boolean).join(" · "))}</div>` : ""}</td>
      <td>
        <select class="edit-field edit-field-sm kp-role-select" data-entry-index="${index}">
          ${roleOptions}
        </select>
        <input type="text" class="edit-field edit-field-sm kp-other-role-input" data-entry-index="${index}" value="${escapeAttr(person.other_project_role_category || "")}" placeholder="Specify other role…" style="margin-top:.25rem;${showOtherRole ? "" : "display:none;"}">
        ${person.credential ? `<div class="sub-dim mono" style="margin-top:.25rem">${escapeHtml(person.credential)}</div>` : ""}
      </td>
      <td>${renderAttachmentCell(index, "biosketch", bio, Boolean(attach.biosketch?.required))}<br>${renderAttachmentCell(index, "current_pending_support", sup, false)}</td>
      <td>${warnings.length ? `<ul class="warn-list">${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>` : '<span class="sub-dim">—</span>'}</td>
    </tr>`;
  }).join("");

  return `<div class="kp-manifest"><table><thead><tr><th>Actions</th><th>Name</th><th>Contact</th><th>Organization</th><th>Role / Credential</th><th>Attachments</th><th>Warnings</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderBudgetManifest(manifest) {
  if (!Array.isArray(manifest) || manifest.length === 0) {
    return '<p class="empty-note">No budget manifest loaded yet.</p>';
  }

  function months(value) {
    return value || "";
  }

  function secHdr(label) {
    return `<tr class="bgt-sec-hdr"><td colspan="9">${escapeHtml(label)}</td></tr>`;
  }

  function dataRow({
    name = "",
    role = "",
    cal = "",
    acad = "",
    summ = "",
    pers = "",
    salary = "",
    fringe = "",
    funds = "",
    indent = 0,
  }) {
    const pad = 0.55 + indent * 0.8;
    return `<tr class="bgt-data-row">
      <td class="bgt-label" style="padding-left:${pad}rem">${escapeHtml(name)}</td>
      <td class="bgt-detail">${escapeHtml(role)}</td>
      <td class="bgt-num">${escapeHtml(cal)}</td>
      <td class="bgt-num">${escapeHtml(acad)}</td>
      <td class="bgt-num">${escapeHtml(summ)}</td>
      <td class="bgt-num">${escapeHtml(pers)}</td>
      <td class="bgt-amt">${escapeHtml(salary)}</td>
      <td class="bgt-amt">${escapeHtml(fringe)}</td>
      <td class="bgt-amt bgt-funds">${escapeHtml(funds)}</td>
    </tr>`;
  }

  function totalRow(label, amount, className = "bgt-total-row") {
    return `<tr class="${className}">
      <td colspan="8" class="bgt-total-label">${escapeHtml(label)}</td>
      <td class="bgt-amt bgt-funds">${escapeHtml(amount)}</td>
    </tr>`;
  }

  const thead = `<thead><tr class="bgt-col-hdr">
    <th class="bgt-label">Description</th>
    <th class="bgt-detail">Role / Notes</th>
    <th class="bgt-num">Cal Mo</th>
    <th class="bgt-num">Acad Mo</th>
    <th class="bgt-num">Sum Mo</th>
    <th class="bgt-num"># Pers</th>
    <th class="bgt-amt">Req Salary</th>
    <th class="bgt-amt">Fringe</th>
    <th class="bgt-amt">Funds Req</th>
  </tr></thead>`;

  const standardOtherPersonnel = [
    ["post_doc_associates", "Post Doctoral Associates"],
    ["graduate_students", "Graduate Students (Research Assistants)"],
    ["undergraduate_students", "Undergraduate Students"],
    ["secretarial_clerical", "Secretarial / Clerical"],
  ];

  return manifest.map((entry, index) => {
    const org = entry.organization || {};
    const just = entry.budget_justification || {};
    const justName = fileLabel(just.path || "");
    const periods = Array.isArray(entry.periods) ? entry.periods.map((period) => {
      const periodIndex = period.period_index || "?";
      const start = period.start_date || "";
      const end = period.end_date || "";
      const rows = [];

      const secA = period.section_a || {};
      rows.push(secHdr("A. SENIOR / KEY PERSONNEL"));
      for (const kp of secA.key_persons || []) {
        rows.push(dataRow({
          name: `${kp.first_name || ""} ${kp.last_name || ""}`.trim(),
          role: kp.project_role || "",
          cal: months(kp.calendar_months),
          acad: months(kp.academic_months),
          summ: months(kp.summer_months),
          salary: formatMoney(kp.requested_salary),
          fringe: formatMoney(kp.fringe_benefits),
          funds: formatMoney(kp.funds_requested),
        }));
      }
      rows.push(totalRow("Section A Total", formatMoney(secA.total)));

      const secB = period.section_b || {};
      rows.push(secHdr("B. OTHER PERSONNEL"));
      for (const [key, label] of standardOtherPersonnel) {
        const item = secB[key];
        if (item && (item.funds_requested || item.requested_salary)) {
          rows.push(dataRow({
            name: label,
            cal: months(item.calendar_months),
            acad: months(item.academic_months),
            summ: months(item.summer_months),
            pers: item.number_of_personnel || "",
            salary: formatMoney(item.requested_salary),
            fringe: formatMoney(item.fringe_benefits),
            funds: formatMoney(item.funds_requested),
          }));
        }
      }
      for (const other of secB.other_personnel || []) {
        rows.push(dataRow({
          name: other.project_role || "Other Personnel",
          cal: months(other.calendar_months),
          acad: months(other.academic_months),
          summ: months(other.summer_months),
          pers: other.number_of_personnel || "",
          salary: formatMoney(other.requested_salary),
          fringe: formatMoney(other.fringe_benefits),
          funds: formatMoney(other.funds_requested),
        }));
      }
      rows.push(totalRow("Section B Total", formatMoney(secB.total_funds)));

      const secC = period.section_c || {};
      if ((secC.items || []).length || secC.total) {
        rows.push(secHdr("C. EQUIPMENT"));
        for (const item of secC.items || []) {
          rows.push(dataRow({
            name: item.description || item.item || "",
            funds: formatMoney(item.cost || item.funds_requested),
          }));
        }
        rows.push(totalRow("Section C Total", formatMoney(secC.total)));
      }

      const secD = period.section_d || {};
      if (secD.total_travel_cost) {
        rows.push(secHdr("D. TRAVEL"));
        rows.push(dataRow({
          name: "Total Travel Costs",
          funds: formatMoney(secD.total_travel_cost),
        }));
      }

      const secE = period.section_e || {};
      if (secE.total_cost || secE.other_cost) {
        rows.push(secHdr("E. PARTICIPANT / TRAINEE SUPPORT COSTS"));
        if (secE.other_description || secE.other_cost) {
          rows.push(dataRow({
            name: secE.other_description || "Other Costs",
            funds: formatMoney(secE.other_cost),
          }));
        }
        rows.push(totalRow("Section E Total", formatMoney(secE.total_cost)));
      }

      const secF = period.section_f || {};
      rows.push(secHdr("F. OTHER DIRECT COSTS"));
      const directCostRows = [
        ["Materials and Supplies", secF.materials_supplies],
        ["Publication Costs", secF.publication_costs],
        ["Consultant Services", secF.consultant_services],
        ["ADP / Computer Services", secF.adp_computer_services],
        ["Subawards / Consortium / Contractual", secF.subawards_consortium_contractual_costs],
        ["Equipment / Facility Rental User Fees", secF.equipment_facility_rental_user_fees],
        ["Alterations / Renovations", secF.alterations_renovations],
      ];
      for (const [label, value] of directCostRows) {
        if (value) {
          rows.push(dataRow({ name: label, funds: formatMoney(value) }));
        }
      }
      for (const other of secF.other_items || []) {
        rows.push(dataRow({
          name: other.description || "Other",
          funds: formatMoney(other.cost),
        }));
      }
      rows.push(totalRow("Section F Total", formatMoney(secF.total)));

      rows.push(totalRow("G. TOTAL DIRECT COSTS (A - F)", formatMoney(period.direct_costs), "bgt-subtotal-row"));

      const secH = period.section_h || {};
      rows.push(secHdr("H. INDIRECT COSTS"));
      for (const indirect of secH.indirect_costs || []) {
        const notes = [];
        if (indirect.rate) notes.push(`Rate: ${indirect.rate}%`);
        if (indirect.base) notes.push(`Base: ${formatMoney(indirect.base)}`);
        rows.push(dataRow({
          name: indirect.cost_type || "",
          role: notes.join(" · "),
          funds: formatMoney(indirect.fund_requested),
        }));
      }
      if (secH.cognizant_agency) {
        rows.push(dataRow({ name: `Cognizant Federal Agency: ${secH.cognizant_agency}` }));
      }
      rows.push(totalRow("Section H Total", formatMoney(secH.total)));

      rows.push(totalRow("I. TOTAL DIRECT AND INDIRECT COSTS (G + H)", formatMoney(period.total_costs), "bgt-subtotal-row"));

      const feeTotal = period.total_costs_fee;
      if (feeTotal && feeTotal !== period.total_costs) {
        rows.push(totalRow("TOTAL COSTS + FEE", formatMoney(feeTotal), "bgt-grand-total-row"));
      }

      return `<div class="budget-period-hdr">Period ${escapeHtml(String(periodIndex))}: ${escapeHtml(start)} – ${escapeHtml(end)}</div>
        <div class="bgt-table-wrap">
          <table class="bgt-table">${thead}<tbody>${rows.join("")}</tbody></table>
        </div>`;
    }).join("") : "";

    return `<div class="card budget-row-card">
      <div class="budget-org">${escapeHtml(org.name || `Budget source ${index + 1}`)}</div>
      <div class="sub-dim" style="font-size:.8rem">${escapeHtml(org.budget_type || "")}${org.uei ? ` &nbsp;|&nbsp; UEI: ${escapeHtml(org.uei)}` : ""}</div>
      ${just.path ? `<div class="sub-info" style="font-size:.8rem;margin:.45rem 0">${icon("file", "icon-status")} Budget Justification: ${escapeHtml(justName)}</div>` : ""}
      <div class="file-link-btn">${renderAttachmentCell(index, "budget_justification", just.path || "", false)}</div>
      ${periods}
    </div>`;
  }).join("");
}

function renderPerformanceSiteManifest(manifest) {
  return manifest.map((entry, index) => {
    const count = (entry.primary_site ? 1 : 0) + ((entry.other_sites || []).length);
    return `<div class="card budget-row-card">
      <div class="budget-org">${escapeHtml(entry.source_pdf || `Performance Site source ${index + 1}`)}</div>
      <div class="sub-info">Sites queued: ${count}</div>
      <div class="sub-info" style="margin:.45rem 0">${icon("file", "icon-status")} Additional Site Attachment: ${escapeHtml(fileLabel(entry.additional_sites_attachment?.path || ""))}</div>
      <div class="file-link-btn">${renderAttachmentCell(index, "additional_sites_attachment", entry.additional_sites_attachment?.path || "", false)}</div>
    </div>`;
  }).join("");
}

function renderAttachmentCell(index, kind, path, required) {
  const label = path ? basename(path) : (required ? "required" : "none");
  const buttonLabel = path ? "Replace" : "Attach";
  return `<button type="button" class="btn-success btn-sm attach-btn" data-entry-index="${index}" data-kind="${escapeAttr(kind)}">${icon("upload", "icon-btn")}${buttonLabel}</button> <span class="${path ? "sub-info" : "sub-dim"}">${escapeHtml(label)}</span>`;
}

function renderEntryActions(index, entry) {
  const includeLabel = entry?.exclude ? "Include" : "Exclude";
  const includeClass = entry?.exclude ? "btn-success" : "btn-warn";
  return `<div class="entry-actions">
    <button type="button" class="${includeClass} btn-sm entry-toggle-btn" data-entry-index="${index}">${icon(entry?.exclude ? "check" : "pause", "icon-btn")}${includeLabel}</button>
    <button type="button" class="btn-danger btn-sm entry-remove-btn" data-entry-index="${index}">${icon("trash", "icon-btn")}Remove</button>
  </div>`;
}

function stepDone(name, manifest, files) {
  const backend = currentState?.backend || null;
  if (name === "fetch-schemas") {
    return false;
  }
  if (isBackendPipelineStep(name)) {
    return backend?.status === "completed" && Array.isArray(manifest) && manifest.length > 0;
  }
  if (name.includes("extract")) {
    return files.filter((file) => file.role === "source-pdf").length > 0;
  }
  if (name.includes("validate")) {
    return false;
  }
  if (name.includes("normalize")) {
    return Array.isArray(manifest) && manifest.length > 0;
  }
  if (name.includes("automate")) {
    return false;
  }
  return false;
}

function bindPageInteractions() {
  document.querySelector("#open-grants-inline")?.addEventListener("click", () => {
    chrome.tabs.create({ url: "https://apply07.grants.gov/" });
  });

  const dropZone = document.querySelector("#drop-zone");
  const pdfInput = document.querySelector("#pdf-file-input");
  dropZone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone?.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone?.addEventListener("drop", async (event) => {
    event.preventDefault();
    dropZone.classList.remove("drag-over");
    await uploadFiles(event.dataTransfer.files);
  });
  pdfInput?.addEventListener("change", async (event) => {
    await uploadFiles(event.target.files);
    event.target.value = "";
  });

  document.querySelector("#manifest-file-input")?.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const manifest = JSON.parse(text);
      const result = await chrome.runtime.sendMessage({
        type: "rrtar:save-manifest",
        formType: activeTab,
        manifest,
      });
      if (!result?.ok) {
        setStatus(result?.error || "Could not save manifest.", "err");
      } else {
        setStatus(`Imported manifest for ${TAB_DEFS[activeTab].title}.`, "");
        await refreshState();
      }
    } catch (error) {
      setStatus(`Manifest import failed: ${String(error)}`, "err");
    }
    event.target.value = "";
  });

  document.querySelector("#export-manifest-btn")?.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(currentState?.manifest || [], null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${activeTab}-manifest.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  });

  document.querySelector("#clear-manifest-btn")?.addEventListener("click", async () => {
    const result = await chrome.runtime.sendMessage({ type: "rrtar:clear-manifest", formType: activeTab });
    if (!result?.ok) {
      setStatus(result?.error || "Could not clear manifest.", "err");
      return;
    }
    setStatus(`Cleared ${TAB_DEFS[activeTab].manifestTitle}.`, "");
    await refreshState();
  });

  document.querySelector("#add-contact-btn")?.addEventListener("click", async () => {
    await openContactModal();
  });

  document.querySelectorAll("[data-remove-file]").forEach((button) => {
    button.addEventListener("click", async () => {
      const result = await chrome.runtime.sendMessage({
        type: "rrtar:remove-file",
        id: button.getAttribute("data-remove-file"),
      });
      if (!result?.ok) {
        setStatus(result?.error || "Could not remove file.", "err");
        return;
      }
      await refreshState();
      setStatus("", "");
    });
  });

  document.querySelectorAll(".attach-btn").forEach((button) => {
    button.addEventListener("click", () => openAttachmentPicker(button));
  });

  document.querySelectorAll(".entry-toggle-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      await updateManifest((manifest) => {
        const entry = manifest[Number(button.getAttribute("data-entry-index") || -1)];
        if (entry) {
          entry.exclude = !entry.exclude;
        }
      }, "Updated include state.");
    });
  });

  document.querySelectorAll(".entry-remove-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      await updateManifest((manifest) => {
        const index = Number(button.getAttribute("data-entry-index") || -1);
        if (index >= 0) {
          manifest.splice(index, 1);
        }
      }, "Removed manifest entry.");
    });
  });

  document.querySelectorAll(".kp-role-select").forEach((select) => {
    select.addEventListener("change", async () => {
      const index = Number(select.getAttribute("data-entry-index") || -1);
      const otherInput = document.querySelector(`.kp-other-role-input[data-entry-index="${index}"]`);
      const role = normalizeProjectRoleValue(select.value);
      if (otherInput) {
        otherInput.style.display = role === "Other (Specify)" ? "" : "none";
        if (role !== "Other (Specify)") {
          otherInput.value = "";
        }
      }
      await updateManifest((manifest) => {
        const person = manifest[index]?.person;
        if (!person) return;
        person.project_role = role;
        person.other_project_role_category = role === "Other (Specify)" ? String(otherInput?.value || "").trim() : "";
      }, "Updated project role.");
    });
  });

  document.querySelectorAll(".kp-other-role-input").forEach((input) => {
    input.addEventListener("change", async () => {
      const index = Number(input.getAttribute("data-entry-index") || -1);
      await updateManifest((manifest) => {
        const person = manifest[index]?.person;
        if (!person) return;
        person.other_project_role_category = String(input.value || "").trim();
      }, "Updated other project role.");
    });
  });

  document.querySelectorAll("[data-step]").forEach((button) => {
    button.addEventListener("click", async () => {
      const step = button.getAttribute("data-step");
      if (step === TAB_DEFS[activeTab].automateStep) {
        await runAutomate();
        return;
      }
      if (isBackendPipelineStep(step)) {
        await runBackendPipeline(step);
        return;
      }
      setStatus(`${step} is shown for parity with ui.py, but it is not ported to clientside yet.`, "warn");
    });
  });

  document.querySelector("#automate-btn")?.addEventListener("click", runAutomate);
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList || []).filter((file) => file.name.toLowerCase().endsWith(".pdf"));
  if (!files.length) {
    setStatus("Please choose PDF files only.", "warn");
    return;
  }
  for (const file of files) {
    const serialized = await serializeFileForMessage(file);
    const result = await chrome.runtime.sendMessage({
      type: "rrtar:put-file",
      formType: activeTab,
      role: "source-pdf",
      file: serialized,
      meta: { name: file.name, mimeType: file.type, size: file.size },
    });
    if (!result?.ok) {
      setStatus(result?.error || `Could not store ${file.name}.`, "err");
      return;
    }
  }
  await refreshState();
  setStatus("", "");
}

async function openAttachmentPicker(button) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".pdf,application/pdf";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    if (!file) return;
    const serialized = await serializeFileForMessage(file);
    const putResult = await chrome.runtime.sendMessage({
      type: "rrtar:put-file",
      formType: activeTab,
      role: button.getAttribute("data-kind") || "attachment",
      file: serialized,
      meta: { name: file.name, mimeType: file.type, size: file.size },
    });
    if (!putResult?.ok) {
      setStatus(putResult?.error || "Could not attach file.", "err");
      return;
    }
    const manifest = structuredClone(currentState?.manifest || []);
    applyAttachmentPath(
      manifest,
      activeTab,
      Number(button.getAttribute("data-entry-index") || 0),
      button.getAttribute("data-kind") || "",
      putResult.path,
    );
    const saveResult = await chrome.runtime.sendMessage({
      type: "rrtar:save-manifest",
      formType: activeTab,
      manifest,
    });
    if (!saveResult?.ok) {
      setStatus(saveResult?.error || "Could not update manifest attachment.", "err");
      return;
    }
    setStatus(`Updated attachment for ${TAB_DEFS[activeTab].title}.`, "");
    await refreshState();
  });
  input.click();
}

async function runAutomate() {
  const payload = await chrome.runtime.sendMessage({
    type: "rrtar:prepare-autofill",
    formType: activeTab,
  });
  if (!payload?.ok) {
    setStatus(payload?.error || "Could not prepare autofill payload.", "err");
    return;
  }
  if (!Array.isArray(payload.manifest) || payload.manifest.length === 0) {
    setStatus(`No manifest loaded for ${TAB_DEFS[activeTab].title}.`, "warn");
    return;
  }
  const tabs = await chrome.tabs.query({ currentWindow: true });
  const tab = tabs.find((item) => item.active && String(item.url || "").includes("grants.gov"))
    || tabs.find((item) => String(item.url || "").includes("grants.gov"));
  if (!tab?.id) {
    setStatus("Open the target Grants.gov form tab in this window, then run Automate again.", "warn");
    return;
  }
  const detection = await chrome.tabs.sendMessage(tab.id, { type: "rrtar:detect-form" });
  if (!detection?.ok || !detection.detection?.supported) {
    setStatus(detection?.error || "No supported Grants.gov form detected in the active tab.", "err");
    return;
  }
  if (detection.detection.formType !== activeTab) {
    setStatus(`Detected ${detection.detection.formType}, but this dashboard tab is ${activeTab}. Switch tabs or open the correct Grants.gov form.`, "warn");
    return;
  }
  setStatus(`Running ${TAB_DEFS[activeTab].automateStep} against the active Grants.gov tab...`, "", { sticky: true });
  const result = await chrome.tabs.sendMessage(tab.id, {
    type: "rrtar:autofill-manifest",
    payload,
  });
  setStatus(typeof result === "string" ? result : JSON.stringify(result, null, 2), result?.ok ? "" : "err");
}

async function runBackendPipeline(step) {
  if (!Array.isArray(currentState?.files) || !currentState.files.some((file) => file.role === "source-pdf")) {
    setStatus(`Stage at least one PDF for ${TAB_DEFS[activeTab].title} before running ${step}.`, "warn");
    return;
  }
  setStatus(`Running ${step} on the backend for ${TAB_DEFS[activeTab].title}...`, "", { sticky: true });
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:run-backend-pipeline",
    formType: activeTab,
  });
  if (!result?.ok) {
    setStatus(result?.error || `Backend pipeline failed during ${step}.`, "err");
    return;
  }
  await refreshState();
  const warningCount = Array.isArray(result.preview?.warnings) ? result.preview.warnings.length : 0;
  const backendStatus = result.backend?.status || "completed";
  setStatus(`Backend ${backendStatus} for ${TAB_DEFS[activeTab].title}. Loaded ${result.manifest?.length || 0} manifest entries${warningCount ? ` with ${warningCount} warning${warningCount === 1 ? "" : "s"}` : ""}.`, warningCount ? "warn" : "");
}

async function updateManifest(mutator, successMessage) {
  const manifest = structuredClone(currentState?.manifest || []);
  mutator(manifest);
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:save-manifest",
    formType: activeTab,
    manifest,
  });
  if (!result?.ok) {
    setStatus(result?.error || "Could not update manifest.", "err");
    return;
  }
  setStatus(successMessage, "");
  await refreshState();
}

async function openContactModal() {
  if (activeTab !== "keyperson") {
    return;
  }
  currentContactResults = [];
  contactSearchInput.value = "";
  contactSearchMeta.textContent = "Search bundled contacts by name, email, department, unit, location, or title.";
  contactSearchResults.innerHTML = '<p class="empty-note">Type a search above to load matching contacts from the bundled dataset.</p>';
  contactModal.hidden = false;
  document.body.classList.add("modal-open");
  await performContactSearch("");
  window.setTimeout(() => contactSearchInput.focus(), 0);
}

function closeContactModal() {
  contactModal.hidden = true;
  document.body.classList.remove("modal-open");
}

async function performContactSearch(query) {
  contactSearchMeta.textContent = "Searching contacts...";
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:search-contacts",
    query,
    limit: 24,
  });
  if (!result?.ok) {
    currentContactResults = [];
    contactSearchMeta.textContent = result?.error || "Could not search contacts.";
    contactSearchResults.innerHTML = "";
    return;
  }
  currentContactResults = Array.isArray(result.results) ? result.results : [];
  const count = currentContactResults.length;
  contactSearchMeta.textContent = result.query
    ? `${count} match${count === 1 ? "" : "es"} for “${result.query}”.`
    : `${count} contacts shown from bundled contacts.json.`;
  if (!count) {
    contactSearchResults.innerHTML = '<p class="empty-note">No contacts matched that search.</p>';
    return;
  }
  contactSearchResults.innerHTML = currentContactResults.map((item, index) => `
    <div class="contact-result">
      <div class="contact-result-copy">
        <div class="contact-result-title">${escapeHtml(item.label)}</div>
        <div class="contact-result-meta">${escapeHtml([item.email, item.jobTitle].filter(Boolean).join(" · ") || "No email or title")}</div>
        <div class="contact-result-sub">${escapeHtml([item.department || item.unit, item.division, item.workLocation || formatCampusBox(item.campusBox)].filter(Boolean).join(" · ") || "No department or location metadata")}</div>
      </div>
      <button type="button" class="btn-success btn-sm contact-add-btn" data-contact-index="${index}">${icon("check", "icon-btn")}Add</button>
    </div>
  `).join("");
  contactSearchResults.querySelectorAll(".contact-add-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const contact = currentContactResults[Number(button.getAttribute("data-contact-index") || -1)];
      if (!contact?.manifestEntry) {
        setStatus("Contact payload was incomplete.", "err");
        return;
      }
      await updateManifest((manifest) => {
        const entry = structuredClone(contact.manifestEntry);
        entry.source_index = manifest.filter((row) => row?.source_element === "ContactDirectory").length;
        manifest.push(entry);
      }, `Added ${contact.label} from bundled contacts.`);
      closeContactModal();
    });
  });
}

function applyAttachmentPath(manifest, formType, entryIndex, kind, path) {
  const entry = manifest[entryIndex];
  if (!entry) return;
  if (formType === "keyperson") {
    entry.attachments = entry.attachments || {};
    entry.attachments[kind] = entry.attachments[kind] || {};
    entry.attachments[kind].path = path;
    return;
  }
  if (formType === "budget" && kind === "budget_justification") {
    entry.budget_justification = entry.budget_justification || {};
    entry.budget_justification.path = path;
    return;
  }
  if (formType === "performance-site" && kind === "additional_sites_attachment") {
    entry.additional_sites_attachment = entry.additional_sites_attachment || {};
    entry.additional_sites_attachment.path = path;
  }
}

function setStatus(message, kind, options = {}) {
  window.clearTimeout(statusHideTimer);
  statusHideTimer = 0;
  if (!message) {
    statusStrip.hidden = true;
    statusStrip.textContent = "";
    statusStrip.className = "status-strip";
    return;
  }
  statusStrip.hidden = false;
  statusStrip.textContent = message;
  statusStrip.className = `status-strip ${kind || ""}`.trim();
  if (!options.sticky) {
    statusHideTimer = window.setTimeout(() => {
      statusStrip.hidden = true;
      statusStrip.textContent = "";
      statusStrip.className = "status-strip";
      statusHideTimer = 0;
    }, STATUS_TIMEOUT_MS);
  }
}

function isBackendPipelineStep(step) {
  return [
    "extract",
    "validate",
    "normalize",
    "extract-budget",
    "normalize-budget",
    "extract-performance-site",
    "normalize-performance-site",
  ].includes(String(step || ""));
}

function icon(name, classes = "") {
  const asset = ICONS[name];
  if (!asset) {
    return "";
  }
  const size = classes.includes("icon-chip") ? "lg" : "sm";
  const className = ["icon", classes].filter(Boolean).join(" ");
  return `<span class="${className}"><img src="${asset[size]}" alt="" aria-hidden="true"></span>`;
}

function basename(path) {
  return String(path || "").split(/[\\/]/).pop() || "";
}

function fileLabel(path) {
  const text = String(path || "").trim();
  if (!text) return "none";
  if (text.startsWith("rrtar-file://")) return "clientside file attached";
  return basename(text) || text;
}

async function serializeFileForMessage(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  return {
    name: file.name || "upload.pdf",
    mimeType: file.type || "application/pdf",
    size: Number(file.size || bytes.byteLength || 0),
    base64: uint8ArrayToBase64(bytes),
  };
}

function uint8ArrayToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let idx = 0; idx < bytes.length; idx += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(idx, idx + chunkSize));
  }
  return btoa(binary);
}

function formatSize(size) {
  const number = Number(size || 0);
  if (number < 1024) return `${number} bytes`;
  return `${Math.round(number / 1024)} KB`;
}

function formatMoney(value) {
  if (value == null || value === "") return "—";
  const number = Number(String(value).replace(/[$,\s]/g, ""));
  if (!Number.isFinite(number)) return String(value);
  return `$${number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function buildKeypersonRoleOptions(currentRole) {
  const options = [...KEYPERSON_ROLE_OPTIONS];
  if (currentRole && !options.includes(currentRole)) {
    options.push(currentRole);
  }
  return options;
}

function normalizeProjectRoleValue(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const normalized = text.toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (normalized === "PI" || normalized === "PDPI" || normalized === "PRINCIPALINVESTIGATOR") {
    return "PD/PI";
  }
  if (normalized === "COPI" || normalized === "COINVESTIGATOR") {
    return "Co-Investigator";
  }
  if (normalized === "COPDPI" || normalized === "MULTIPLEPI") {
    return "Co-PD/PI";
  }
  if (normalized === "OTHERSIGNIFICANTCONTRIBUTOR" || normalized === "OSC") {
    return "Other (Specify)";
  }
  return text;
}

function normalizeFormType(value) {
  return value === "budget" || value === "performance-site" ? value : "keyperson";
}

function formatCampusBox(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return /^campus box\b/i.test(text) ? text : `Campus Box ${text}`;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

contactModalCloseBtn?.addEventListener("click", closeContactModal);
contactModalCancelBtn?.addEventListener("click", closeContactModal);
contactModal?.addEventListener("click", (event) => {
  if (event.target === contactModal) {
    closeContactModal();
  }
});
contactSearchInput?.addEventListener("input", async (event) => {
  await performContactSearch(event.target.value || "");
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !contactModal.hidden) {
    closeContactModal();
  }
});
