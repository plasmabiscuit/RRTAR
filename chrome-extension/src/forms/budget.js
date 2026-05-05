(function registerBudgetAutofill() {
  const common = self.RRTARAutofillCommon;
  const MODAL_ID = "seniorKeyPersonDetail";
  const SECTION_B_ROW = {
    post_doc_associates: 1,
    graduate_students: 2,
    undergraduate_students: 3,
    secretarial_clerical: 4,
  };

  self.RRTARBudgetAutofill = {
    async run(payload) {
      const detection = common.detectCurrentFrameForm();
      if (detection.formType !== "budget") {
        return { ok: false, error: "Budget autofill ran outside the R&R Budget frame." };
      }

      const entries = Array.isArray(payload?.manifest) ? payload.manifest : [];
      if (!entries.length) {
        return { ok: false, error: "Budget manifest is empty." };
      }

      const stats = { fields: 0, uploads: 0, errors: [], skipped: [] };
      for (const entry of entries) {
        const periods = Array.isArray(entry?.periods) ? entry.periods : [];
        for (const period of periods) {
          const periodIndex = Number(period?.period_index || 0);
          if (!periodIndex) {
            stats.errors.push("Budget period is missing period_index.");
            continue;
          }
          await ensureBudgetPeriodExists(periodIndex);
          await fillSectionA(periodIndex, period?.section_a?.key_persons || [], stats);
          fillSectionB(periodIndex, period?.section_b || {}, stats);
          await fillSectionC(periodIndex, period?.section_c || {}, stats);
          fillSectionD(periodIndex, period?.section_d || {}, stats);
          fillSectionE(periodIndex, period?.section_e || {}, stats);
          fillSectionF(periodIndex, period?.section_f || {}, stats);
          await fillSectionH(periodIndex, period?.section_h || {}, stats);
          fillSectionJ(periodIndex, period || {}, stats);
          await attachPeriodFiles(periodIndex, entry, period || {}, stats);
        }

        const justResult = await common.uploadAttachmentFromJob(
          document,
          "budgetJustificationFile",
          entry?.budget_justification?.path || "",
        );
        common.accumulate(justResult, stats, "uploads", "budgetJustificationFile");
      }

      return {
        ok: stats.errors.length === 0,
        formType: "budget",
        entryCount: entries.length,
        fieldsWritten: stats.fields,
        uploadsWritten: stats.uploads,
        skipped: stats.skipped,
        errors: stats.errors,
      };
    },
  };

  async function ensureBudgetPeriodExists(periodIndex) {
    const markers = [
      `budgetPeriodStartDate${periodIndex}`,
      `keyPersonAdd${periodIndex}`,
      `listD${periodIndex}_1`,
    ];
    if (markers.some((id) => document.getElementById(id))) {
      return;
    }
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const clicked = common.clickFirstButtonByText(document, ["Add Period"]);
      if (!clicked) {
        throw new Error(`Add Period button not found for period ${periodIndex}.`);
      }
      await common.waitFor(() => markers.some((id) => document.getElementById(id)), 8000, 150);
      if (markers.some((id) => document.getElementById(id))) {
        return;
      }
    }
    throw new Error(`Budget period ${periodIndex} did not appear.`);
  }

  async function fillSectionA(periodIndex, persons, stats) {
    const addButtonId = `keyPersonAdd${periodIndex}`;
    let existingRows = common.countExisting(document, `#requestedSalaryA${periodIndex}_{N}`, 12);
    const targetRows = periodIndex === 1 ? persons.length : persons.length + 1;

    if (periodIndex > 1 && existingRows < targetRows) {
      for (let idx = existingRows + 1; idx <= targetRows; idx += 1) {
        await openModal(addButtonId);
        await closeModal();
      }
      existingRows = common.countExisting(document, `#requestedSalaryA${periodIndex}_{N}`, 12);
    }

    for (let personIndex = 0; personIndex < persons.length; personIndex += 1) {
      const rowIndex = periodIndex === 1 ? personIndex + 1 : personIndex + 2;
      if (periodIndex === 1) {
        await openModal(addButtonId);
        fillModalPerson(persons[personIndex], stats);
        await closeModal();
      } else {
        fillSectionARow(periodIndex, rowIndex, persons[personIndex], stats);
      }
    }

    if (periodIndex > 1 && existingRows > targetRows) {
      for (let rowIndex = existingRows; rowIndex > targetRows; rowIndex -= 1) {
        clearSectionARow(periodIndex, rowIndex, stats);
        const deleteButton = document.getElementById(`deleteSeniorkeyperson${periodIndex}_${rowIndex}`);
        if (deleteButton) {
          deleteButton.click();
          await common.sleep(150);
        }
      }
    }
  }

  async function openModal(buttonId) {
    const button = document.getElementById(buttonId);
    if (!button) {
      throw new Error(`Key Person add button not found: ${buttonId}`);
    }
    button.click();
    await common.waitFor(() => {
      const modal = document.getElementById(MODAL_ID);
      return modal && (modal.classList.contains("in") || /display:\s*block/i.test(modal.getAttribute("style") || ""));
    }, 8000, 150);
    await common.sleep(200);
  }

  async function closeModal() {
    const button = document.querySelector(".modal-footer .btn-primary");
    if (!button) {
      throw new Error("Budget modal save button not found.");
    }
    button.click();
    await common.waitFor(() => {
      const modal = document.getElementById(MODAL_ID);
      return modal && !modal.classList.contains("in");
    }, 8000, 150);
    await common.sleep(150);
  }

  function fillModalPerson(person, stats) {
    const prefix = String(person?.prefix || "");
    const suffix = String(person?.suffix || "");
    const fields = {
      prefix: prefix.toUpperCase().includes("OTHER") ? "" : prefix,
      otherPrefix: prefix.toUpperCase().includes("OTHER") ? prefix : "",
      firstName: person?.first_name || "",
      middleName: person?.middle_name || "",
      lastName: person?.last_name || "",
      suffix: suffix.toUpperCase().includes("OTHER") ? "" : suffix,
      otherSuffix: suffix.toUpperCase().includes("OTHER") ? suffix : "",
      projectRole: person?.project_role || "",
      baseSalary: person?.base_salary || "",
      calendarMonths: person?.calendar_months || "",
      academicMonths: person?.academic_months || "",
      summerMonths: person?.summer_months || "",
      requestedSalary: person?.requested_salary || "",
      fringeBenefits: person?.fringe_benefits || "",
    };

    for (const [id, value] of Object.entries(fields)) {
      const result = id === "projectRole"
        ? common.selectControlValue(document, id, value)
        : common.setControlValue(document, id, value);
      common.accumulate(result, stats, "fields", id);
    }
  }

  function fillSectionARow(periodIndex, rowIndex, person, stats) {
    const fields = {
      [`baseSalaryA${periodIndex}_${rowIndex}`]: person?.base_salary || "",
      [`calendarMonthsA${periodIndex}_${rowIndex}`]: person?.calendar_months || "",
      [`academicMonthsA${periodIndex}_${rowIndex}`]: person?.academic_months || "",
      [`summerMonthsA${periodIndex}_${rowIndex}`]: person?.summer_months || "",
      [`requestedSalaryA${periodIndex}_${rowIndex}`]: person?.requested_salary || "",
      [`fringeBenefitsA${periodIndex}_${rowIndex}`]: person?.fringe_benefits || "",
    };
    writeFieldMap(fields, stats, { allowEmpty: true });
  }

  function clearSectionARow(periodIndex, rowIndex, stats) {
    fillSectionARow(periodIndex, rowIndex, {}, stats);
  }

  function fillSectionB(periodIndex, section, stats) {
    for (const [key, rowIndex] of Object.entries(SECTION_B_ROW)) {
      fillSectionBRow(periodIndex, rowIndex, section?.[key] || {}, stats);
    }

    const otherRows = Array.isArray(section?.other_personnel) ? section.other_personnel : [];
    const existingDynamic = common.countExisting(document, `#numberOfPersonnel${periodIndex}_{N}`, 20, 5);
    const neededDynamic = 4 + otherRows.length;

    for (let rowIndex = Math.max(existingDynamic + 1, 5); rowIndex <= neededDynamic; rowIndex += 1) {
      const clicked = common.clickFirstButtonByText(document, ["Add Additional Other Personnel"]);
      if (!clicked) {
        stats.errors.push(`Could not add Other Personnel row ${rowIndex} for period ${periodIndex}.`);
        break;
      }
    }

    for (let idx = 0; idx < otherRows.length; idx += 1) {
      fillSectionBRow(periodIndex, idx + 5, otherRows[idx], stats);
    }
    for (let rowIndex = 5 + otherRows.length; rowIndex <= Math.max(existingDynamic, neededDynamic); rowIndex += 1) {
      fillSectionBRow(periodIndex, rowIndex, {}, stats);
    }
  }

  function fillSectionBRow(periodIndex, rowIndex, row, stats) {
    if (rowIndex >= 5) {
      const roleResult = common.setControlValue(document, `listB${periodIndex}_${rowIndex}`, row?.project_role || "", { allowEmpty: true });
      common.accumulate(roleResult, stats, "fields", `listB${periodIndex}_${rowIndex}`);
    }
    writeFieldMap({
      [`numberOfPersonnel${periodIndex}_${rowIndex}`]: row?.number_of_personnel || "",
      [`calendarMonthsB${periodIndex}_${rowIndex}`]: row?.calendar_months || "",
      [`academicMonthsB${periodIndex}_${rowIndex}`]: row?.academic_months || "",
      [`summerMonthsB${periodIndex}_${rowIndex}`]: row?.summer_months || "",
      [`requestedSalaryB${periodIndex}_${rowIndex}`]: row?.requested_salary || "",
      [`fringeBenefitsB${periodIndex}_${rowIndex}`]: row?.fringe_benefits || "",
    }, stats, { allowEmpty: true });
  }

  async function fillSectionC(periodIndex, section, stats) {
    const items = Array.isArray(section?.items) ? section.items : [];
    for (let idx = 0; idx < items.length; idx += 1) {
      const rowIndex = idx + 1;
      if (rowIndex > 1 && !document.getElementById(`equipmentItem${periodIndex}_${rowIndex}`)) {
        const clicked = common.clickFirstButtonByText(document, ["Add Additional Equipment"]);
        if (!clicked) {
          stats.errors.push(`Could not add equipment row ${rowIndex} for period ${periodIndex}.`);
          continue;
        }
        await common.waitFor(() => document.getElementById(`equipmentItem${periodIndex}_${rowIndex}`), 6000, 120);
      }
      writeFieldMap({
        [`equipmentItem${periodIndex}_${rowIndex}`]: items[idx]?.item || "",
        [`fundsRequestedC${periodIndex}_${rowIndex}`]: items[idx]?.funds_requested || "",
      }, stats, { allowEmpty: true });
    }
    const existingRows = common.countExisting(document, `#equipmentItem${periodIndex}_{N}`, 12);
    for (let rowIndex = items.length + 1; rowIndex <= existingRows; rowIndex += 1) {
      writeFieldMap({
        [`equipmentItem${periodIndex}_${rowIndex}`]: "",
        [`fundsRequestedC${periodIndex}_${rowIndex}`]: "",
      }, stats, { allowEmpty: true });
    }
  }

  function fillSectionD(periodIndex, section, stats) {
    writeFieldMap({
      [`listD${periodIndex}_1`]: section?.domestic_travel_cost || section?.total_travel_cost || "",
      [`listD${periodIndex}_2`]: section?.foreign_travel_cost || "",
    }, stats, { allowEmpty: true });
  }

  function fillSectionE(periodIndex, section, stats) {
    writeFieldMap({
      [`fundsRequestedE${periodIndex}_1`]: section?.tuition_fees_health_insurance || "",
      [`fundsRequestedE${periodIndex}_2`]: section?.stipends || "",
      [`fundsRequestedE${periodIndex}_3`]: section?.travel || "",
      [`fundsRequestedE${periodIndex}_4`]: section?.subsistence || "",
      [`listE${periodIndex}_5`]: section?.other_description || "",
      [`fundsRequestedE${periodIndex}_5`]: section?.other_cost || "",
      [`numberOfParticipants${periodIndex}`]: section?.number_of_participants || section?.number_of_participants_trainees || "",
    }, stats, { allowEmpty: true });
  }

  function fillSectionF(periodIndex, section, stats) {
    const fixed = {
      [`fundsRequestedF${periodIndex}_1`]: section?.materials_supplies || "",
      [`fundsRequestedF${periodIndex}_2`]: section?.publication_costs || "",
      [`fundsRequestedF${periodIndex}_3`]: section?.consultant_services || "",
      [`fundsRequestedF${periodIndex}_4`]: section?.adp_computer_services || "",
      [`fundsRequestedF${periodIndex}_5`]: section?.subawards_consortium_contractual_costs || "",
      [`fundsRequestedF${periodIndex}_6`]: section?.equipment_facility_rental_user_fees || "",
      [`fundsRequestedF${periodIndex}_7`]: section?.alterations_renovations || "",
    };
    writeFieldMap(fixed, stats, { allowEmpty: true });

    const otherItems = Array.isArray(section?.other_items) ? section.other_items : [];
    let rowIndex = 8;
    for (const item of otherItems) {
      writeFieldMap({
        [`listF${periodIndex}_${rowIndex}`]: item?.description || "",
        [`fundsRequestedF${periodIndex}_${rowIndex}`]: item?.cost || "",
      }, stats, { allowEmpty: true });
      rowIndex += 1;
    }
    for (; rowIndex < 18; rowIndex += 1) {
      writeFieldMap({
        [`listF${periodIndex}_${rowIndex}`]: "",
        [`fundsRequestedF${periodIndex}_${rowIndex}`]: "",
      }, stats, { allowEmpty: true });
    }
  }

  async function fillSectionH(periodIndex, section, stats) {
    const rows = Array.isArray(section?.indirect_costs) ? section.indirect_costs : [];
    for (let idx = 0; idx < rows.length; idx += 1) {
      const rowIndex = idx + 1;
      if (rowIndex > 1 && !document.getElementById(`indirectCostType${periodIndex}_${rowIndex}`)) {
        const clicked = common.clickFirstButtonByText(document, ["Add Additional Indirect Cost"]);
        if (!clicked) {
          stats.errors.push(`Could not add indirect cost row ${rowIndex} for period ${periodIndex}.`);
          continue;
        }
        await common.waitFor(() => document.getElementById(`indirectCostType${periodIndex}_${rowIndex}`), 6000, 120);
      }
      writeFieldMap({
        [`indirectCostType${periodIndex}_${rowIndex}`]: rows[idx]?.cost_type || "",
        [`indirectCostRate${periodIndex}_${rowIndex}`]: rows[idx]?.rate || "",
        [`indirectCostBase${periodIndex}_${rowIndex}`]: rows[idx]?.base || "",
        [`fundsRequestedH${periodIndex}_${rowIndex}`]: rows[idx]?.fund_requested || "",
      }, stats, { allowEmpty: true });
    }

    const existingRows = common.countExisting(document, `#indirectCostType${periodIndex}_{N}`, 6);
    for (let rowIndex = rows.length + 1; rowIndex <= existingRows; rowIndex += 1) {
      writeFieldMap({
        [`indirectCostType${periodIndex}_${rowIndex}`]: "",
        [`indirectCostRate${periodIndex}_${rowIndex}`]: "",
        [`indirectCostBase${periodIndex}_${rowIndex}`]: "",
        [`fundsRequestedH${periodIndex}_${rowIndex}`]: "",
      }, stats, { allowEmpty: true });
    }

    const agencyResult = common.setControlValue(document, `cognizantFederalAgency${periodIndex}`, section?.cognizant_agency || "", { allowEmpty: true });
    common.accumulate(agencyResult, stats, "fields", `cognizantFederalAgency${periodIndex}`);
  }

  function fillSectionJ(periodIndex, period, stats) {
    const feeResult = common.setControlValue(
      document,
      `totalFundsRequestedJ${periodIndex}`,
      resolveFee(period),
      { allowEmpty: true },
    );
    common.accumulate(feeResult, stats, "fields", `totalFundsRequestedJ${periodIndex}`);
  }

  async function attachPeriodFiles(periodIndex, entry, period, stats) {
    const attachmentSpec = periodAttachmentSpec(entry, period);
    const seniorResult = await common.uploadAttachmentFromJob(
      document,
      `seniorKeyPersonFile${periodIndex}`,
      attachmentSpec.senior_key_persons,
    );
    common.accumulate(seniorResult, stats, "uploads", `seniorKeyPersonFile${periodIndex}`);

    const equipmentResult = await common.uploadAttachmentFromJob(
      document,
      `equipmentFile${periodIndex}`,
      attachmentSpec.equipment,
    );
    common.accumulate(equipmentResult, stats, "uploads", `equipmentFile${periodIndex}`);
  }

  function periodAttachmentSpec(entry, period) {
    const periodIndex = String(period?.period_index || "");
    const sources = [
      entry?.period_attachments?.[periodIndex] || {},
      period?.attachments || {},
    ];
    const merged = Object.assign({}, ...sources);
    return {
      senior_key_persons: pickFirst(merged, [
        "senior_key_persons",
        "senior_key_person",
        "senior_key_person_attachment",
        "key_persons",
        "key_person_attachment",
      ]),
      equipment: pickFirst(merged, ["equipment", "equipment_attachment"]),
    };
  }

  function pickFirst(mapping, keys) {
    for (const key of keys) {
      if (mapping?.[key]) {
        return String(mapping[key]);
      }
    }
    return "";
  }

  function resolveFee(period) {
    if (period?.fee != null && String(period.fee).trim()) {
      return String(period.fee);
    }
    const totalWithFee = parseAmount(period?.total_costs_fee);
    const totalCosts = parseAmount(period?.total_costs);
    if (totalWithFee == null || totalCosts == null) {
      return "";
    }
    const delta = totalWithFee - totalCosts;
    return delta > 0 ? delta.toFixed(2) : "";
  }

  function parseAmount(value) {
    const text = String(value == null ? "" : value).replace(/[$,\s]/g, "");
    if (!text) {
      return null;
    }
    const number = Number(text);
    return Number.isFinite(number) ? number : null;
  }

  function writeFieldMap(mapping, stats, options = {}) {
    for (const [id, value] of Object.entries(mapping)) {
      const result = common.setControlValue(document, id, value, options);
      common.accumulate(result, stats, "fields", id);
    }
  }
})();
