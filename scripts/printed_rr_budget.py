"""
Parse flattened/non-XFA RR_Budget_3_0 print PDFs into RR_Budget_3_0 XML.

This targets PDFs exported from systems like Streamlyne or Grants.gov that are
visually structured like the official Research & Related Budget form, but do not
contain XFA payloads.
"""

from __future__ import annotations

import dataclasses
import decimal
import re
from pathlib import Path
from typing import Optional

import pdfplumber
from lxml import etree


D = decimal.Decimal
ZERO = D("0.00")

NS_RR = "http://apply.grants.gov/forms/RR_Budget_3_0-V3.0"
NS_GLOBLIB = "http://apply.grants.gov/system/GlobalLibrary-V2.0"

q_rr = lambda tag: f"{{{NS_RR}}}{tag}"
q_globlib = lambda tag: f"{{{NS_GLOBLIB}}}{tag}"

MONEY_RE = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")
PERIOD_HEADER_RE = re.compile(r"RESEARCH\s*&\s*RELATED BUDGET - Budget Period (\d+)", re.IGNORECASE)
SECTION_CDE_RE = re.compile(r"RESEARCH\s*&\s*RELATED BUDGET - SECTION C, D, & E, Budget Period (\d+)", re.IGNORECASE)
SECTION_FK_RE = re.compile(r"RESEARCH\s*&\s*RELATED BUDGET - SECTIONS F-K, Budget Period (\d+)", re.IGNORECASE)
ROLE_CONTINUATION_RE = re.compile(r"^[A-Z][A-Z\-/ ]+$")


@dataclasses.dataclass
class KeyPerson:
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    project_role: str = ""
    base_salary: str = ""
    calendar_months: str = ""
    academic_months: str = ""
    summer_months: str = ""
    requested_salary: str = ""
    fringe_benefits: str = ""
    funds_requested: str = ""


@dataclasses.dataclass
class OtherPersonnelRow:
    number_of_personnel: str = ""
    project_role: str = ""
    calendar_months: str = ""
    academic_months: str = ""
    summer_months: str = ""
    requested_salary: str = ""
    fringe_benefits: str = ""
    funds_requested: str = ""


@dataclasses.dataclass
class EquipmentItem:
    item: str = ""
    funds_requested: str = ""


@dataclasses.dataclass
class IndirectCostRow:
    cost_type: str = ""
    rate: str = ""
    base: str = ""
    fund_requested: str = ""


@dataclasses.dataclass
class PeriodData:
    period_index: int
    start_date: str = ""
    end_date: str = ""
    key_persons: list[KeyPerson] = dataclasses.field(default_factory=list)
    key_person_total: str = ""
    other_personnel: dict[str, OtherPersonnelRow] = dataclasses.field(default_factory=dict)
    other_personnel_other_rows: list[OtherPersonnelRow] = dataclasses.field(default_factory=list)
    other_personnel_total_number: str = ""
    other_personnel_total_funds: str = ""
    total_compensation: str = ""
    equipment_items: list[EquipmentItem] = dataclasses.field(default_factory=list)
    equipment_total: str = ""
    travel_domestic: str = ""
    travel_foreign: str = ""
    travel_total: str = ""
    participant_tuition: str = ""
    participant_stipends: str = ""
    participant_travel: str = ""
    participant_subsistence: str = ""
    participant_other_description: str = "Other"
    participant_other_cost: str = ""
    participant_count: str = ""
    participant_total: str = ""
    materials_supplies: str = ""
    publication_costs: str = ""
    consultant_services: str = ""
    adp_computer_services: str = ""
    subawards_consortium_contractual_costs: str = ""
    equipment_facility_rental_user_fees: str = ""
    alterations_renovations: str = ""
    other_direct_items: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    other_direct_total: str = ""
    direct_costs: str = ""
    indirect_costs: list[IndirectCostRow] = dataclasses.field(default_factory=list)
    indirect_total: str = ""
    cognizant_agency: str = ""
    total_costs: str = ""
    total_costs_fee: str = ""


@dataclasses.dataclass
class PrintedRRBudget:
    uei: str = ""
    organization_name: str = ""
    budget_type: str = "Project"
    periods: list[PeriodData] = dataclasses.field(default_factory=list)


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def extract_lines(pdf_path: Path) -> list[str]:
    lines: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            for raw in text.splitlines():
                line = clean_line(raw)
                if line:
                    lines.append(line)
    return lines


def detect_printed_rr_budget(lines: list[str]) -> bool:
    return any("RESEARCH & RELATED BUDGET - Budget Period" in line for line in lines)


def _to_money(text: str) -> str:
    m = MONEY_RE.search(text)
    return m.group(0).replace(",", "") if m else ""


def _money_values(text: str) -> list[str]:
    return [m.replace(",", "") for m in MONEY_RE.findall(text)]


def _norm_date(text: str) -> str:
    month, day, year = text.split("/")
    return f"{year}-{month}-{day}"


def _prepend_line_continuations(lines: list[str]) -> list[str]:
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (
            merged
            and ROLE_CONTINUATION_RE.match(line)
            and merged[-1].startswith(tuple(f"{n} ." for n in range(1, 10)))
        ):
            merged[-1] = f"{merged[-1]} {line}"
            i += 1
            continue
        merged.append(line)
        i += 1
    return merged


def _split_period_blocks(lines: list[str]) -> tuple[dict[int, list[str]], dict[int, list[str]], dict[int, list[str]], list[str]]:
    section_ab: dict[int, list[str]] = {}
    section_cde: dict[int, list[str]] = {}
    section_fk: dict[int, list[str]] = {}
    cumulative: list[str] = []
    current_kind: Optional[str] = None
    current_period: Optional[int] = None

    for line in lines:
        if m := PERIOD_HEADER_RE.match(line):
            current_kind = "ab"
            current_period = int(m.group(1))
            section_ab.setdefault(current_period, []).append(line)
            continue
        if m := SECTION_CDE_RE.match(line):
            current_kind = "cde"
            current_period = int(m.group(1))
            section_cde.setdefault(current_period, []).append(line)
            continue
        if m := SECTION_FK_RE.match(line):
            current_kind = "fk"
            current_period = int(m.group(1))
            section_fk.setdefault(current_period, []).append(line)
            continue
        if "RESEARCH & RELATED BUDGET - Cumulative Budget" in line:
            current_kind = "cum"
            current_period = None
            cumulative.append(line)
            continue

        if current_kind == "ab" and current_period is not None:
            section_ab[current_period].append(line)
        elif current_kind == "cde" and current_period is not None:
            section_cde[current_period].append(line)
        elif current_kind == "fk" and current_period is not None:
            section_fk[current_period].append(line)
        elif current_kind == "cum":
            cumulative.append(line)

    return section_ab, section_cde, section_fk, cumulative


def _parse_key_person_row(line: str) -> KeyPerson:
    amount_matches = list(MONEY_RE.finditer(line))
    if len(amount_matches) < 7:
        raise ValueError(f"Could not parse key person row: {line}")
    amount_texts = [m.group(0).replace(",", "") for m in amount_matches[:7]]
    prefix = line[:amount_matches[0].start()].strip()
    prefix = re.sub(r"^\d+\s*\.\s*", "", prefix).strip()
    role_match = re.match(r"(?P<name>.+?)\s+(?P<role>(?:PD/PI|CO-\s*INVESTIGATOR|CO-INVESTIGATOR|INVESTIGATOR|CO-PI|PI))\s*$", prefix)
    if not role_match:
        role_match = re.match(r"(?P<name>.+?)\s+(?P<role>[A-Z][A-Z/\- ]+)$", prefix)
    if not role_match:
        raise ValueError(f"Could not split key person name/role from: {line}")
    full_name = role_match.group("name").strip()
    role = role_match.group("role").replace("CO- ", "CO-").strip()
    parts = full_name.split()
    if len(parts) == 1:
        first, middle, last = "", "", parts[0]
    elif len(parts) == 2:
        first, middle, last = parts[0], "", parts[1]
    else:
        first, middle, last = parts[0], " ".join(parts[1:-1]), parts[-1]
    return KeyPerson(
        first_name=first,
        middle_name=middle,
        last_name=last,
        project_role=role,
        base_salary=amount_texts[0],
        calendar_months=amount_texts[1],
        academic_months=amount_texts[2],
        summer_months=amount_texts[3],
        requested_salary=amount_texts[4],
        fringe_benefits=amount_texts[5],
        funds_requested=amount_texts[6],
    )


def _parse_other_personnel_row(line: str) -> OtherPersonnelRow:
    values = _money_values(line)
    m = re.match(r"^(?P<num>\d+)\s+(?P<role>.+?)\s+(?P<cal>\d+\.\d{2})\s+(?P<acad>\d+\.\d{2})\s+(?P<sum>\d+\.\d{2})\s+(?P<salary>\d+\.\d{2})\s+(?P<fringe>\d+\.\d{2})\s+(?P<funds>\d+\.\d{2})$", line.replace(",", ""))
    if not m:
        raise ValueError(f"Could not parse other personnel row: {line}")
    return OtherPersonnelRow(
        number_of_personnel=m.group("num"),
        project_role=m.group("role").strip(),
        calendar_months=m.group("cal"),
        academic_months=m.group("acad"),
        summer_months=m.group("sum"),
        requested_salary=m.group("salary"),
        fringe_benefits=m.group("fringe"),
        funds_requested=m.group("funds"),
    )


def _parse_period_header(lines: list[str], period_index: int) -> tuple[str, str, str, str]:
    uei = ""
    budget_type = "Project"
    org = ""
    start = ""
    end = ""
    for line in lines:
        if line.startswith("*UEI:"):
            uei = line.split(":", 1)[1].strip()
        elif line.startswith("*Budget Type:"):
            budget_type = "Subaward/Consortium" if "Subaward/Consortium" in line and "Project" not in line.split(":")[-1].strip() else "Project"
        elif line.startswith("Enter name of Organization:"):
            org = line.split(":", 1)[1].strip()
        elif line.startswith("Organization:"):
            org = line.split(":", 1)[1].strip()
        elif "*Start Date:" in line and "*End Date:" in line:
            dates = DATE_RE.findall(line)
            if len(dates) >= 2:
                start, end = _norm_date(dates[0]), _norm_date(dates[1])
    return uei, budget_type, org, start, end


def _parse_period(ab_lines: list[str], cde_lines: list[str], fk_lines: list[str], period_index: int) -> PeriodData:
    uei, budget_type, org, start, end = _parse_period_header(ab_lines + cde_lines + fk_lines, period_index)
    period = PeriodData(period_index=period_index, start_date=start, end_date=end)

    i = 0
    while i < len(ab_lines):
        line = ab_lines[i]
        if re.match(r"^\d+\s+\.", line) or re.match(r"^\d+\s\.", line):
            period.key_persons.append(_parse_key_person_row(line))
        elif re.match(r"^\d+\s+(Post Doctoral Associates|Graduate Students|Undergraduate Students|Secretarial/Clerical|Other|Other Professionals|Allocated Admin Support)\b", line):
            row = _parse_other_personnel_row(line)
            role_map = {
                "Post Doctoral Associates": "post_doc_associates",
                "Graduate Students": "graduate_students",
                "Undergraduate Students": "undergraduate_students",
                "Secretarial/Clerical": "secretarial_clerical",
            }
            key = role_map.get(row.project_role)
            if key:
                period.other_personnel[key] = row
            else:
                period.other_personnel_other_rows.append(row)
        elif line.startswith("Additional Senior Key Persons:") and "Total Senior/Key Person" in line:
            monies = _money_values(line)
            if monies:
                period.key_person_total = monies[-1]
        elif line.startswith("Total Salary, Wages and Fringe Benefits (A+B)"):
            period.total_compensation = _money_values(line)[-1]
        elif "Total Number Other Personnel" in line and "Total Other Personnel" in line:
            m = re.match(r"^(?P<num>\d+)\s+Total Number Other Personnel Total Other Personnel\s+(?P<funds>\d+\.\d{2})$", line.replace(",", ""))
            if m:
                period.other_personnel_total_number = m.group("num")
                period.other_personnel_total_funds = m.group("funds")
        i += 1

    for line in cde_lines:
        if re.match(r"^\d+\s+\.\s+.+\s+\d+\.\d{2}$", line.replace(",", "")) and "Equipment" in line:
            no_commas = line.replace(",", "")
            m = re.match(r"^\d+\s+\.\s+(?P<item>.+?)\s+(?P<funds>\d+\.\d{2})$", no_commas)
            if m:
                period.equipment_items.append(EquipmentItem(item=m.group("item").strip(), funds_requested=m.group("funds")))
        elif line.startswith("Total Equipment"):
            monies = _money_values(line)
            if monies:
                period.equipment_total = monies[-1]
        elif line.startswith("1. Domestic Travel Costs"):
            period.travel_domestic = _money_values(line)[-1]
        elif line.startswith("2. Foreign Travel Costs"):
            period.travel_foreign = _money_values(line)[-1]
        elif line.startswith("Total Travel Cost"):
            period.travel_total = _money_values(line)[-1]
        elif line.startswith("1. Tuition/Fees/Health Insurance"):
            period.participant_tuition = _money_values(line)[-1]
        elif line.startswith("2. Stipends"):
            period.participant_stipends = _money_values(line)[-1]
        elif line.startswith("3. Travel"):
            period.participant_travel = _money_values(line)[-1]
        elif line.startswith("4. Subsistence"):
            period.participant_subsistence = _money_values(line)[-1]
        elif line.startswith("5. Other:"):
            period.participant_other_description = line.split(":", 1)[1].rsplit(" ", 1)[0].strip() or "Other"
            period.participant_other_cost = _money_values(line)[-1]
        elif "Number of Participants/Trainees" in line and "Total Participant Trainee Support Costs" in line:
            m = re.match(r"^(?P<count>\d+)\s+Number of Participants/Trainees Total Participant Trainee Support Costs\s+(?P<total>\d+\.\d{2})$", line.replace(",", ""))
            if m:
                period.participant_count = m.group("count")
                period.participant_total = m.group("total")

    for line in fk_lines:
        monies = _money_values(line)
        if line.startswith("1. Materials and Supplies"):
            period.materials_supplies = monies[-1]
        elif line.startswith("2. Publication Costs"):
            period.publication_costs = monies[-1]
        elif line.startswith("3. Consultant Services"):
            period.consultant_services = monies[-1]
        elif line.startswith("4. ADP/Computer Services"):
            period.adp_computer_services = monies[-1]
        elif line.startswith("5. Subawards/Consortium/Contractual Costs"):
            period.subawards_consortium_contractual_costs = monies[-1]
        elif line.startswith("6. Equipment or Facility Rental/User Fees"):
            period.equipment_facility_rental_user_fees = monies[-1]
        elif line.startswith("7. Alterations and Renovations"):
            period.alterations_renovations = monies[-1]
        elif re.match(r"^(8|9|10|11|12|13|14|15|16|17)\.", line):
            desc = line.rsplit(" ", 1)[0].split(".", 1)[1].strip()
            period.other_direct_items.append((desc, monies[-1]))
        elif line.startswith("Total Other Direct Costs"):
            period.other_direct_total = monies[-1]
        elif line.startswith("Total Direct Costs (A thru F)"):
            period.direct_costs = monies[-1]
        elif re.match(r"^\d+\s+\.\s+.+\s+\d+\.\d{2}\s+\d+\.\d{2}\s+\d+\.\d{2}$", line.replace(",", "")):
            m = re.match(r"^\d+\s+\.\s+(?P<type>.+?)\s+(?P<rate>\d+\.\d{2})\s+(?P<base>\d+\.\d{2})\s+(?P<funds>\d+\.\d{2})$", line.replace(",", ""))
            if m:
                period.indirect_costs.append(IndirectCostRow(
                    cost_type=m.group("type").strip(),
                    rate=m.group("rate"),
                    base=m.group("base"),
                    fund_requested=m.group("funds"),
                ))
        elif line.startswith("Total Indirect Costs"):
            period.indirect_total = monies[-1]
        elif line.startswith("Cognizant Federal Agency"):
            period.cognizant_agency = line.split("Agency", 1)[1].strip()
        elif line.startswith("Total Direct and Indirect Institutional Costs (G + H)"):
            period.total_costs = monies[-1]
        elif line.startswith("Total Costs and Fee (I + J)"):
            period.total_costs_fee = monies[-1]

    return period, uei, budget_type, org


def parse_printed_rr_budget(lines: list[str]) -> PrintedRRBudget:
    lines = _prepend_line_continuations(lines)
    if not detect_printed_rr_budget(lines):
        raise ValueError("Not a printed RR Budget layout")

    ab_blocks, cde_blocks, fk_blocks, _cumulative = _split_period_blocks(lines)
    period_indexes = sorted(set(ab_blocks) | set(cde_blocks) | set(fk_blocks))
    if not period_indexes:
        raise ValueError("No budget period blocks detected")

    budget = PrintedRRBudget()
    for idx in period_indexes:
        period, uei, budget_type, org = _parse_period(
            ab_blocks.get(idx, []),
            cde_blocks.get(idx, []),
            fk_blocks.get(idx, []),
            idx,
        )
        budget.periods.append(period)
        if uei and not budget.uei:
            budget.uei = uei
        if org and not budget.organization_name:
            budget.organization_name = org
        if budget_type:
            budget.budget_type = budget_type

    return budget


def _add_text(parent: etree._Element, tag: str, value: str) -> etree._Element:
    el = etree.SubElement(parent, q_rr(tag))
    el.text = value
    return el


def build_rr_budget_xml(budget: PrintedRRBudget) -> etree._ElementTree:
    root = etree.Element(q_rr("RR_Budget_3_0"), nsmap={"RR_Budget_3_0": NS_RR, "globLib": NS_GLOBLIB})
    root.set(q_rr("FormVersion"), "3.0")
    _add_text(root, "SAMUEI", budget.uei)
    _add_text(root, "BudgetType", budget.budget_type)
    _add_text(root, "OrganizationName", budget.organization_name)

    for period in budget.periods:
        year_el = etree.SubElement(root, q_rr("BudgetYear"))
        _add_text(year_el, "BudgetPeriodStartDate", period.start_date)
        _add_text(year_el, "BudgetPeriodEndDate", period.end_date)

        kp_root = etree.SubElement(year_el, q_rr("KeyPersons"))
        for person in period.key_persons:
            kp_el = etree.SubElement(kp_root, q_rr("KeyPerson"))
            name_el = etree.SubElement(kp_el, q_rr("Name"))
            etree.SubElement(name_el, q_globlib("FirstName")).text = person.first_name
            if person.middle_name:
                etree.SubElement(name_el, q_globlib("MiddleName")).text = person.middle_name
            etree.SubElement(name_el, q_globlib("LastName")).text = person.last_name
            _add_text(kp_el, "ProjectRole", person.project_role)
            _add_text(kp_el, "BaseSalary", person.base_salary)
            _add_text(kp_el, "CalendarMonths", person.calendar_months)
            _add_text(kp_el, "AcademicMonths", person.academic_months)
            _add_text(kp_el, "SummerMonths", person.summer_months)
            _add_text(kp_el, "RequestedSalary", person.requested_salary)
            _add_text(kp_el, "FringeBenefits", person.fringe_benefits)
            _add_text(kp_el, "FundsRequested", person.funds_requested)
        _add_text(kp_root, "TotalFundForKeyPersons", period.key_person_total)

        op_root = etree.SubElement(year_el, q_rr("OtherPersonnel"))
        for tag, key in [
            ("PostDocAssociates", "post_doc_associates"),
            ("GraduateStudents", "graduate_students"),
            ("UndergraduateStudents", "undergraduate_students"),
            ("SecretarialClerical", "secretarial_clerical"),
        ]:
            row = period.other_personnel.get(key)
            if row is None:
                continue
            row_el = etree.SubElement(op_root, q_rr(tag))
            _add_text(row_el, "NumberOfPersonnel", row.number_of_personnel)
            _add_text(row_el, "ProjectRole", row.project_role)
            _add_text(row_el, "CalendarMonths", row.calendar_months)
            _add_text(row_el, "AcademicMonths", row.academic_months)
            _add_text(row_el, "SummerMonths", row.summer_months)
            _add_text(row_el, "RequestedSalary", row.requested_salary)
            _add_text(row_el, "FringeBenefits", row.fringe_benefits)
            _add_text(row_el, "FundsRequested", row.funds_requested)
        for row in period.other_personnel_other_rows:
            row_el = etree.SubElement(op_root, q_rr("Other"))
            _add_text(row_el, "NumberOfPersonnel", row.number_of_personnel)
            _add_text(row_el, "ProjectRole", row.project_role)
            _add_text(row_el, "CalendarMonths", row.calendar_months)
            _add_text(row_el, "AcademicMonths", row.academic_months)
            _add_text(row_el, "SummerMonths", row.summer_months)
            _add_text(row_el, "RequestedSalary", row.requested_salary)
            _add_text(row_el, "FringeBenefits", row.fringe_benefits)
            _add_text(row_el, "FundsRequested", row.funds_requested)
        _add_text(op_root, "OtherPersonnelTotalNumber", period.other_personnel_total_number)
        _add_text(op_root, "TotalOtherPersonnelFund", period.other_personnel_total_funds)
        _add_text(year_el, "TotalCompensation", period.total_compensation)

        eq_root = etree.SubElement(year_el, q_rr("Equipment"))
        if period.equipment_items:
            for item in period.equipment_items:
                item_el = etree.SubElement(eq_root, q_rr("EquipmentList"))
                _add_text(item_el, "EquipmentItem", item.item)
                _add_text(item_el, "FundsRequested", item.funds_requested)
        else:
            item_el = etree.SubElement(eq_root, q_rr("EquipmentList"))
            _add_text(item_el, "EquipmentItem", "")
            _add_text(item_el, "FundsRequested", "")
        _add_text(eq_root, "TotalFund", period.equipment_total)

        tr_root = etree.SubElement(year_el, q_rr("Travel"))
        _add_text(tr_root, "DomesticTravelCost", period.travel_domestic)
        _add_text(tr_root, "ForeignTravelCost", period.travel_foreign)
        _add_text(tr_root, "TotalTravelCost", period.travel_total)

        pt_root = etree.SubElement(year_el, q_rr("ParticipantTraineeSupportCosts"))
        _add_text(pt_root, "TuitionFeesHealthInsurance", period.participant_tuition)
        _add_text(pt_root, "Stipends", period.participant_stipends)
        _add_text(pt_root, "Travel", period.participant_travel)
        _add_text(pt_root, "Subsistence", period.participant_subsistence)
        other_el = etree.SubElement(pt_root, q_rr("Other"))
        _add_text(other_el, "Description", period.participant_other_description)
        _add_text(other_el, "Cost", period.participant_other_cost)
        _add_text(pt_root, "NumberOfParticipantsTrainees", period.participant_count)
        _add_text(pt_root, "TotalCost", period.participant_total)

        odc_root = etree.SubElement(year_el, q_rr("OtherDirectCosts"))
        _add_text(odc_root, "MaterialsSupplies", period.materials_supplies)
        _add_text(odc_root, "PublicationCosts", period.publication_costs)
        _add_text(odc_root, "ConsultantServices", period.consultant_services)
        _add_text(odc_root, "ADPComputerServices", period.adp_computer_services)
        _add_text(odc_root, "SubawardsConsortiumContractualCosts", period.subawards_consortium_contractual_costs)
        _add_text(odc_root, "EquipmentFacilityRentalUserFees", period.equipment_facility_rental_user_fees)
        _add_text(odc_root, "AlterationsRenovations", period.alterations_renovations)
        for idx in range(1, 11):
            node = etree.SubElement(odc_root, q_rr(f"OtherDirectCost{idx}"))
            if idx <= len(period.other_direct_items):
                desc, cost = period.other_direct_items[idx - 1]
                _add_text(node, "Description", desc)
                _add_text(node, "Cost", cost)
            else:
                _add_text(node, "Description", "")
                _add_text(node, "Cost", "")
        _add_text(odc_root, "TotalOtherDirectCost", period.other_direct_total)

        _add_text(year_el, "DirectCosts", period.direct_costs)

        ic_root = etree.SubElement(year_el, q_rr("IndirectCosts"))
        if period.indirect_costs:
            for row in period.indirect_costs:
                ic_el = etree.SubElement(ic_root, q_rr("IndirectCost"))
                _add_text(ic_el, "CostType", row.cost_type)
                _add_text(ic_el, "Rate", row.rate)
                _add_text(ic_el, "Base", row.base)
                _add_text(ic_el, "FundRequested", row.fund_requested)
        else:
            ic_el = etree.SubElement(ic_root, q_rr("IndirectCost"))
            _add_text(ic_el, "CostType", "")
            _add_text(ic_el, "Rate", "")
            _add_text(ic_el, "Base", "")
            _add_text(ic_el, "FundRequested", "")
        _add_text(ic_root, "TotalIndirectCosts", period.indirect_total)
        _add_text(ic_root, "CognizantFederalAgency", period.cognizant_agency)

        _add_text(year_el, "TotalCosts", period.total_costs)
        _add_text(year_el, "TotalCostsFee", period.total_costs_fee)

    return etree.ElementTree(root)
