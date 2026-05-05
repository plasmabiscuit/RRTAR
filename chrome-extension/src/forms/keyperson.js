(function registerKeyPersonAutofill() {
  const common = self.RRTARAutofillCommon;

  const FIELD_SPECS = [
    ["personPrefix{N}", "prefix"],
    ["personOtherPrefix{N}", "prefix", { allowEmpty: false }],
    ["personFirstName{N}", "first_name"],
    ["personMiddleName{N}", "middle_name"],
    ["personLastName{N}", "last_name"],
    ["personSuffix{N}", "suffix"],
    ["personOtherSuffix{N}", "suffix", { allowEmpty: false }],
    ["personTitle{N}", "title"],
    ["personOrganization{N}", "organization_name"],
    ["personDepartment{N}", "department"],
    ["personDivision{N}", "division"],
    ["personStreet1{N}", "address.street1"],
    ["personStreet2{N}", "address.street2"],
    ["personCity{N}", "address.city"],
    ["personCounty{N}", "address.county"],
    ["personState{N}", "address.state", { select: true, treatAsState: true }],
    ["personProvince{N}", "address.province"],
    ["personCountry{N}", "address.country"],
    ["personZipCode{N}", "address.postal_code"],
    ["personPhoneNumber{N}", "phone"],
    ["personFaxNumber{N}", "fax"],
    ["personEmail{N}", "email"],
    ["personCredential{N}", "credential"],
    ["personProjectRole{N}", "project_role", { select: true }],
    ["personOtherProjectRole{N}", "other_project_role_category"],
    ["personDegreeType{N}", "degree_type"],
    ["personDegreeYear{N}", "degree_year"],
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
        fillPersonRow(rowNumber, person, stats);
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
    let existing = document.querySelectorAll("[id^='personFirstName']").length;
    while (existing < targetCount) {
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

  function fillPersonRow(rowNumber, person, stats) {
    for (const [template, fieldPath, options] of FIELD_SPECS) {
      const id = template.replace("{N}", String(rowNumber));
      let value = readField(person, fieldPath);

      if (id.startsWith("personOtherPrefix") && !isOtherValue(person.prefix)) {
        value = "";
      }
      if (id.startsWith("personOtherSuffix") && !isOtherValue(person.suffix)) {
        value = "";
      }
      if (id.startsWith("personOtherProjectRole") && !isOtherValue(person.project_role)) {
        value = "";
      }

      const result = options?.select
        ? common.selectControlValue(document, id, value, options)
        : common.setControlValue(document, id, value, options);
      common.accumulate(result, stats, "fields", id);
    }
  }

  async function uploadPersonAttachments(rowNumber, attachments, stats) {
    const bioResult = await common.uploadAttachmentFromJob(
      document,
      `personBioSketchsFile${rowNumber}`,
      attachments?.biosketch?.path || "",
    );
    common.accumulate(bioResult, stats, "uploads", `personBioSketchsFile${rowNumber}`);

    const supportResult = await common.uploadAttachmentFromJob(
      document,
      `personSupportsFile${rowNumber}`,
      attachments?.current_pending_support?.path || "",
    );
    common.accumulate(supportResult, stats, "uploads", `personSupportsFile${rowNumber}`);
  }

  function readField(person, path) {
    return String(path.split(".").reduce((value, part) => (value && value[part] != null ? value[part] : ""), person) || "");
  }

  function isOtherValue(value) {
    const text = String(value || "").toUpperCase();
    return text.includes("OTHER");
  }
})();
