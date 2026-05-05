(function registerKeyPersonAutofill() {
  const common = self.RRTARAutofillCommon;

  const FIELD_SPECS = [
    ["Prefix", "prefix"],
    ["OtherPrefix", "prefix", { allowEmpty: false }],
    ["FirstName", "first_name"],
    ["MiddleName", "middle_name"],
    ["LastName", "last_name"],
    ["Suffix", "suffix"],
    ["OtherSuffix", "suffix", { allowEmpty: false }],
    ["Title", "title"],
    ["Organization", "organization_name"],
    ["Department", "department"],
    ["Division", "division"],
    ["Street1", "address.street1"],
    ["Street2", "address.street2"],
    ["City", "address.city"],
    ["County", "address.county"],
    ["State", "address.state", { treatAsState: true }],
    ["Province", "address.province"],
    ["Country", "address.country"],
    ["ZipCode", "address.postal_code"],
    ["PhoneNumber", "phone"],
    ["FaxNumber", "fax"],
    ["Email", "email"],
    ["Credential", "credential"],
    ["ProjectRole", "project_role"],
    ["OtherProjectRole", "other_project_role_category"],
    ["DegreeType", "degree_type"],
    ["DegreeYear", "degree_year"],
  ];

  self.RRTARKeyPersonAutofill = {
    async run(payload) {
      const detection = common.detectCurrentFrameForm();
      if (detection.formType !== "keyperson") {
        return {
          ok: false,
          error: "Key Person autofill ran outside the R&R Senior/Key Person frame.",
        };
      }

      const entries = Array.isArray(payload?.manifest)
        ? payload.manifest.filter((entry) => !entry?.exclude)
        : [];
      if (!entries.length) {
        return { ok: false, error: "Key Person manifest is empty." };
      }

      const stats = { fields: 0, uploads: 0, errors: [], skipped: [] };
      await ensureProfileSlots(entries.length);

      for (let index = 0; index < entries.length; index += 1) {
        const person = entries[index]?.person || {};
        const rowNumber = index + 1;
        fillPersonProfile(rowNumber, person, stats);
        await uploadPersonAttachments(rowNumber, entries[index]?.attachments || {}, stats);
      }

      return {
        ok: stats.errors.length === 0,
        formType: "keyperson",
        entryCount: entries.length,
        fieldsWritten: stats.fields,
        uploadsWritten: stats.uploads,
        skipped: stats.skipped,
        warnings: common.manifestWarnings(entries),
        errors: stats.errors,
      };
    },
  };

  async function ensureProfileSlots(targetCount) {
    const targetAdditionalProfiles = Math.max(0, Number(targetCount || 0));
    let existing = document.querySelectorAll("[id^='personFirstName']").length;
    while (existing < targetAdditionalProfiles) {
      const addButton = document.querySelector("#addProfile button");
      if (!addButton) {
        throw new Error("Add Profile button not found.");
      }
      addButton.click();
      const expected = existing + 1;
      await common.waitFor(() => document.getElementById(`personFirstName${expected}`), 8000, 150);
      existing = document.querySelectorAll("[id^='personFirstName']").length;
    }
  }

  function fillPersonProfile(rowNumber, person, stats) {
    for (const [fieldSuffix, fieldPath, options] of FIELD_SPECS) {
      const id = `person${fieldSuffix}${rowNumber}`;
      let value = readField(person, fieldPath);

      if (fieldSuffix === "OtherPrefix" && !isOtherValue(person.prefix)) {
        value = "";
      }
      if (fieldSuffix === "OtherSuffix" && !isOtherValue(person.suffix)) {
        value = "";
      }
      if (fieldSuffix === "OtherProjectRole" && !isOtherValue(person.project_role)) {
        value = "";
      }
      if (fieldSuffix === "ProjectRole") {
        value = normalizeProjectRole(value);
      }

      const result = common.setControlValue(document, id, value, options);
      common.accumulate(result, stats, "fields", id);
    }
  }

  async function uploadPersonAttachments(rowNumber, attachments, stats) {
    const bioId = `personBioSketchsFile${rowNumber}`;
    const bioResult = await common.uploadAttachmentFromJob(
      document,
      bioId,
      attachments?.biosketch?.path || "",
    );
    common.accumulate(bioResult, stats, "uploads", bioId);

    const supportId = `personSupportsFile${rowNumber}`;
    const supportResult = await common.uploadAttachmentFromJob(
      document,
      supportId,
      attachments?.current_pending_support?.path || "",
    );
    common.accumulate(supportResult, stats, "uploads", supportId);
  }

  function readField(person, path) {
    return String(path.split(".").reduce((value, part) => (value && value[part] != null ? value[part] : ""), person) || "");
  }

  function isOtherValue(value) {
    const text = String(value || "").toUpperCase();
    return text.includes("OTHER");
  }

  function normalizeProjectRole(value) {
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
    if (normalized === "COPDPI" || normalized === "CO_PDPI" || normalized === "MULTIPLEPI") {
      return "Co-PD/PI";
    }
    if (normalized === "OTHERSIGNIFICANTCONTRIBUTOR" || normalized === "OSC") {
      return "Other (Specify)";
    }
    return text;
  }
})();
