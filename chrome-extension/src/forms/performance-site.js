(function registerPerformanceSiteAutofill() {
  const common = self.RRTARAutofillCommon;

  const OTHER_IDS = {
    individual: "otherIndividual{N}",
    organization_name: "otherOrganization{N}",
    uei: "otherUEI{N}",
    street1: "otherStreet1{N}",
    street2: "otherStreet2{N}",
    city: "otherCity{N}",
    county: "otherCounty{N}",
    state: "otherState{N}",
    province: "otherProvince{N}",
    country: "otherCountry{N}",
    zip_postal_code: "otherZipCode{N}",
    congressional_district: "otherCongressionalDistrict{N}",
  };

  self.RRTARPerformanceSiteAutofill = {
    async run(payload) {
      const detection = common.detectCurrentFrameForm();
      if (detection.formType !== "performance-site") {
        return {
          ok: false,
          error: "Performance Site autofill ran outside the Project/Performance Site frame.",
        };
      }

      const entries = Array.isArray(payload?.manifest) ? payload.manifest : [];
      if (!entries.length) {
        return { ok: false, error: "Performance Site manifest is empty." };
      }

      const stats = { fields: 0, uploads: 0, errors: [], skipped: [] };
      let nextRowIndex = countExistingOtherRows() + 1;

      for (const entry of entries) {
        for (const site of entrySitesAsAdditional(entry)) {
          const addButton = document.querySelector("#addSite button");
          if (!addButton) {
            stats.errors.push("Additional site add button not found.");
            break;
          }
          addButton.click();
          const rowIndex = nextRowIndex;
          await common.waitFor(() => document.getElementById(`otherOrganization${rowIndex}`) || document.getElementById(`otherCity${rowIndex}`), 8000, 150);
          fillSite(site, rowIndex, stats);
          nextRowIndex += 1;
        }

        const attachResult = await common.uploadAttachmentFromJob(
          document,
          "additionalSiteFile",
          entry?.additional_sites_attachment?.path || "",
        );
        common.accumulate(attachResult, stats, "uploads", "additionalSiteFile");
      }

      return {
        ok: stats.errors.length === 0,
        formType: "performance-site",
        fieldsWritten: stats.fields,
        uploadsWritten: stats.uploads,
        entryCount: entries.length,
        skipped: stats.skipped,
        errors: stats.errors,
      };
    },
  };

  function countExistingOtherRows() {
    return common.countExisting(document, "#otherOrganization{N}", 25);
  }

  function entrySitesAsAdditional(entry) {
    const sites = [];
    if (entry?.primary_site) {
      sites.push(entry.primary_site);
    }
    if (Array.isArray(entry?.other_sites)) {
      sites.push(...entry.other_sites);
    }
    return sites;
  }

  function fillSite(site, rowIndex, stats) {
    const checkResult = common.setCheckboxValue(document, OTHER_IDS.individual.replace("{N}", String(rowIndex)), Boolean(site?.individual));
    common.accumulate(checkResult, stats, "fields", `otherIndividual${rowIndex}`);

    for (const [fieldName, template] of Object.entries(OTHER_IDS)) {
      if (fieldName === "individual") {
        continue;
      }
      const id = template.replace("{N}", String(rowIndex));
      const value = site?.[fieldName] || "";
      const result = (fieldName === "state" || fieldName === "country")
        ? common.selectControlValue(document, id, value, { treatAsState: fieldName === "state" })
        : common.setControlValue(document, id, value);
      common.accumulate(result, stats, "fields", id);
    }
  }
})();
