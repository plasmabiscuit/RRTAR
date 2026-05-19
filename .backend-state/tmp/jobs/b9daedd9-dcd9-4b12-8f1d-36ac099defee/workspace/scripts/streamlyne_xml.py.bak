#!/usr/bin/env python3
"""
Convert a Streamlyne Budget Page Summary PDF into Grants.gov RR_Budget_3_0 XML.

Designed for Streamlyne budget summary PDFs where:
- Salary rows are grouped by personnel category.
- Senior/key person salaries may be split across Academic, Summer, and Calendar categories.
- Effort months appear on the next line as "(1.20 CAL)", "(1.00 ACAD)", "(1.38 SUM)", etc.
- Fringe appears in a separate section and must be matched back to the same person/category.
- Grants.gov RR Budget wants one KeyPerson entry with combined RequestedSalary,
  combined FringeBenefits, combined FundsRequested, and separate CalendarMonths,
  AcademicMonths, and SummerMonths fields where applicable.

Tested conceptually against the uploaded Streamlyne example:
Budget Summary - Genesis 3B_Zhu.pdf

Author: ChatGPT
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import decimal
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pdfplumber
from lxml import etree


D = decimal.Decimal
ZERO = D("0.00")


NS_RR = "http://apply.grants.gov/forms/RR_Budget_3_0-V3.0"
NS_GLOBLIB = "http://apply.grants.gov/system/GlobalLibrary-V2.0"
NS_ATT = "http://apply.grants.gov/system/Attachments-V1.0"
NS_GLOB = "http://apply.grants.gov/system/Global-V1.0"
NS_GRANT = "http://apply.grants.gov/system/MetaGrantApplication"
NS_GRANTWRAPPER = "http://apply.grants.gov/system/MetaGrantApplicationWrapper"
NS_XFA = "http://www.xfa.org/schema/xfa-data/1.0/"

NSMAP = {
    "RR_Budget_3_0": NS_RR,
    "globLib": NS_GLOBLIB,
    "att": NS_ATT,
    "glob": NS_GLOB,
    "grant": NS_GRANT,
    "grantwrapper": NS_GRANTWRAPPER,
    "xfa": NS_XFA,
}


def q_rr(tag: str) -> str:
    return f"{{{NS_RR}}}{tag}"


def q_globlib(tag: str) -> str:
    return f"{{{NS_GLOBLIB}}}{tag}"


def q_att(tag: str) -> str:
    return f"{{{NS_ATT}}}{tag}"


def q_glob(tag: str) -> str:
    return f"{{{NS_GLOB}}}{tag}"


MONEY_RE = re.compile(r"(?<![\w])\$?\(?-?\d{1,3}(?:,\d{3})*\.\d{2}\)?")
DATE_RANGE_RE = re.compile(
    r"(?P<start>\d{2}/\d{2}/\d{4})\s*-\s*(?P<end>\d{2}/\d{2}/\d{4})"
)
EFFORT_RE = re.compile(
    r"^\((?P<months>\d+(?:\.\d+)?)\s*(?P<kind>CAL|Calendar|ACA|ACAD|Academic|SUM|Summer)?\)$",
    re.IGNORECASE,
)
PERIOD_TOKEN_RE = re.compile(r"\bPeriod\s+\d+\b", re.IGNORECASE)


PERSONNEL_CATEGORY_ALIASES = {
    "Faculty Salaries - Academic": "Faculty Salaries - Academic",
    "Faculty Salaries - Summer": "Faculty Salaries - Summer",
    "Faculty Salaries - Calendar": "Faculty Salaries - Calendar",
    "Graduate Student Staff": "Graduate Student Staff",
    "Post-Doctoral Staff": "Post-Doctoral Staff",
    "Postdoctoral Staff": "Post-Doctoral Staff",
    "Post Doctoral Staff": "Post-Doctoral Staff",
    "Research Staff": "Research Staff",
    "Students": "Students",
    "Undergraduate Student Staff": "Students",
    "Secretarial/Clerical": "Secretarial/Clerical",
    "Administrative/Clerical": "Secretarial/Clerical",
    "Other Personnel": "Other Personnel",
}

# Streamlyne categories mapped to RR Budget month fields.
CATEGORY_MONTH_FIELD = {
    "Faculty Salaries - Calendar": "CalendarMonths",
    "Faculty Salaries - Academic": "AcademicMonths",
    "Faculty Salaries - Summer": "SummerMonths",
    "Graduate Student Staff": "CalendarMonths",
    "Post-Doctoral Staff": "CalendarMonths",
    "Research Staff": "CalendarMonths",
    "Students": "CalendarMonths",
    "Secretarial/Clerical": "CalendarMonths",
    "Other Personnel": "CalendarMonths",
}

# Streamlyne personnel category mapped to RR Budget OtherPersonnel buckets.
OTHER_PERSONNEL_BUCKET = {
    "Post-Doctoral Staff": "PostDocAssociates",
    "Graduate Student Staff": "GraduateStudents",
    "Students": "UndergraduateStudents",
    "Secretarial/Clerical": "SecretarialClerical",
    "Research Staff": "Other",
    "Other Personnel": "Other",
}

# Streamlyne non-personnel labels mapped to RR Budget direct cost fields.
# Labels not found here are placed into OtherDirectCost1..10.
DIRECT_COST_FIELD_MAP = {
    "Travel": ("Travel", "TotalTravelCost"),
    "Travel - Professional Development": ("Travel", "TotalTravelCost"),
    "Travel - Domestic": ("Travel", "DomesticTravelCost"),
    "Travel - Foreign": ("Travel", "ForeignTravelCost"),
    "Supplies, General": ("OtherDirectCosts", "MaterialsSupplies"),
    "Materials and Supplies": ("OtherDirectCosts", "MaterialsSupplies"),
    "Professional Services/Consultant": ("OtherDirectCosts", "ConsultantServices"),
    "Professional Services/ Consultant": ("OtherDirectCosts", "ConsultantServices"),
    "Consultant Services": ("OtherDirectCosts", "ConsultantServices"),
    "Publication Costs": ("OtherDirectCosts", "PublicationCosts"),
    "Computer Services": ("OtherDirectCosts", "ADPComputerServices"),
    "Subaward": ("OtherDirectCosts", "SubawardsConsortiumContractualCosts"),
    "Subawards": ("OtherDirectCosts", "SubawardsConsortiumContractualCosts"),
    "Tuition - RA": ("OtherDirectCosts", "Other"),
}


@dataclasses.dataclass
class PersonCost:
    name: str
    category: str
    salary: decimal.Decimal = ZERO
    fringe: decimal.Decimal = ZERO
    calendar_months: decimal.Decimal = ZERO
    academic_months: decimal.Decimal = ZERO
    summer_months: decimal.Decimal = ZERO

    def total(self) -> decimal.Decimal:
        return self.salary + self.fringe

    def add_months(self, field_name: str, months: decimal.Decimal) -> None:
        if field_name == "CalendarMonths":
            self.calendar_months += months
        elif field_name == "AcademicMonths":
            self.academic_months += months
        elif field_name == "SummerMonths":
            self.summer_months += months
        else:
            raise ValueError(f"Unsupported month field: {field_name}")


@dataclasses.dataclass
class BudgetData:
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    proposal_number: Optional[str] = None
    budget_name: Optional[str] = None
    pi_name: Optional[str] = None
    lead_unit_name: Optional[str] = None
    sponsor_name: Optional[str] = None
    sponsor_code: Optional[str] = None

    people_by_name: dict[str, PersonCost] = dataclasses.field(default_factory=dict)
    other_personnel: dict[str, list[PersonCost]] = dataclasses.field(default_factory=lambda: defaultdict(list))

    travel_total: decimal.Decimal = ZERO
    other_direct_cost_fields: dict[str, decimal.Decimal] = dataclasses.field(default_factory=lambda: defaultdict(lambda: ZERO))
    other_direct_cost_lines: list[tuple[str, decimal.Decimal]] = dataclasses.field(default_factory=list)

    total_direct_costs: decimal.Decimal = ZERO
    total_fa_costs: decimal.Decimal = ZERO
    total_project_costs: decimal.Decimal = ZERO
    indirect_rate: Optional[decimal.Decimal] = None
    indirect_base: Optional[decimal.Decimal] = None
    indirect_cost_type: str = "MTDC"


def money_to_decimal(text: str) -> decimal.Decimal:
    cleaned = text.replace("$", "").replace(",", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    value = D(cleaned)
    return -value if negative else value


def fmt_money(value: Optional[decimal.Decimal]) -> str:
    if value is None:
        return ""
    return str(value.quantize(D("0.01"), rounding=decimal.ROUND_HALF_UP))


def fmt_months(value: decimal.Decimal) -> str:
    if value == 0:
        return ""
    return str(value.quantize(D("0.01"), rounding=decimal.ROUND_HALF_UP))


def mmddyyyy_to_iso(date_text: str) -> str:
    month, day, year = date_text.split("/")
    return f"{year}-{month}-{day}"


def clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = line.replace(" / ", "/")
    return line


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


def split_label_and_amounts(line: str) -> tuple[str, list[decimal.Decimal]]:
    matches = list(MONEY_RE.finditer(line))
    if not matches:
        return line.strip(), []

    first_money = matches[0]
    label = line[: first_money.start()].strip()
    amounts = [money_to_decimal(m.group(0)) for m in matches]
    return label, amounts


def line_has_amounts(line: str) -> bool:
    return bool(MONEY_RE.search(line))


def line_is_amounts_only(line: str) -> bool:
    label, amounts = split_label_and_amounts(line)
    return bool(amounts) and not label


def preprocess_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if (
            i + 2 < len(lines)
            and not line_has_amounts(line)
            and line_is_amounts_only(lines[i + 1])
            and not line_has_amounts(lines[i + 2])
            and not EFFORT_RE.match(lines[i + 2])
        ):
            merged.append(f"{line} {lines[i + 2]} {lines[i + 1]}")
            i += 3
            continue

        merged.append(line)
        i += 1

    return merged


def detect_unsupported_multi_period_summary(lines: list[str]) -> str | None:
    period_header_count = max((len(PERIOD_TOKEN_RE.findall(line)) for line in lines), default=0)
    if period_header_count <= 1:
        return None

    has_detail_rows = False
    has_effort_rows = False
    has_wide_amount_rows = False

    for line in lines:
        label, amounts = split_label_and_amounts(line)
        if len(amounts) >= 3:
            has_wide_amount_rows = True
        if EFFORT_RE.match(line):
            has_effort_rows = True
        if canonical_category(label):
            has_detail_rows = True

    if has_wide_amount_rows and not has_effort_rows and not has_detail_rows:
        return (
            "Unsupported Streamlyne layout: multi-period budget summary matrix detected. "
            "This PDF shows cross-period totals only and does not contain the per-period "
            "personnel/direct-cost detail needed to build RR_Budget_3_0 automation data. "
            "Export a detailed per-period Streamlyne budget or separate yearly budget pages instead."
        )

    return None


def canonical_category(label: str) -> Optional[str]:
    label = label.strip()
    return PERSONNEL_CATEGORY_ALIASES.get(label)


def is_section_total(label: str) -> bool:
    lowered = label.lower()
    total_words = [
        "salary",
        "fringe",
        "subtotal",
        "total",
        "calculated direct costs",
        "non-personnel",
        "personnel",
        "indirect costs",
        "totals",
        "mtdc",
    ]
    return any(word in lowered for word in total_words)


def normalize_person_name(label: str) -> str:
    label = re.sub(r"\s+", " ", label).strip()
    label = label.rstrip(",")
    return label


def add_or_update_person(
    budget: BudgetData,
    name: str,
    category: str,
    salary_delta: decimal.Decimal = ZERO,
    fringe_delta: decimal.Decimal = ZERO,
    months_delta: decimal.Decimal = ZERO,
    month_field: Optional[str] = None,
    force_other: bool = False,
    key_person_names: Optional[set[str]] = None,
) -> PersonCost:
    name = normalize_person_name(name)

    is_key_person = False
    if key_person_names and name in key_person_names:
        is_key_person = True
    elif category.startswith("Faculty Salaries"):
        is_key_person = True

    if force_other:
        is_key_person = False

    if is_key_person:
        if name not in budget.people_by_name:
            budget.people_by_name[name] = PersonCost(name=name, category=category)
        person = budget.people_by_name[name]
    else:
        bucket = OTHER_PERSONNEL_BUCKET.get(category, "Other")
        existing = None
        for p in budget.other_personnel[bucket]:
            if p.name == name:
                existing = p
                break
        if existing is None:
            existing = PersonCost(name=name, category=category)
            budget.other_personnel[bucket].append(existing)
        person = existing

    person.salary += salary_delta
    person.fringe += fringe_delta

    if months_delta and month_field:
        person.add_months(month_field, months_delta)

    return person


def parse_budget_pdf(lines: list[str], key_person_names: set[str]) -> BudgetData:
    lines = preprocess_lines(lines)
    unsupported = detect_unsupported_multi_period_summary(lines)
    if unsupported:
        raise ValueError(unsupported)
    budget = BudgetData()

    section: Optional[str] = None
    personnel_subsection: Optional[str] = None  # "salary" or "fringe"
    current_category: Optional[str] = None
    pending_category_prefix: Optional[str] = None
    last_person_context: Optional[tuple[str, str, bool]] = None  # name, category, is_other

    for i, line in enumerate(lines):
        # Header metadata.
        if line.startswith("Proposal Number:"):
            m = re.search(r"Proposal Number:\s*(.*?)\s+Budget Name:\s*(.*)$", line)
            if m:
                budget.proposal_number = m.group(1).strip()
                budget.budget_name = m.group(2).strip()
        elif line.startswith("Principal Investigator:"):
            m = re.search(r"Principal Investigator:\s*(.*?)\s+Lead Unit Name:", line)
            if m:
                budget.pi_name = m.group(1).strip()
                budget.lead_unit_name = line.split("Lead Unit Name:", 1)[1].strip()
        elif line.startswith("Sponsor Name:"):
            m = re.search(r"Sponsor Name:\s*(.*?)\s+Sponsor Code:\s*(.*)$", line)
            if m:
                budget.sponsor_name = m.group(1).strip()
                budget.sponsor_code = m.group(2).strip()

        date_match = DATE_RANGE_RE.search(line)
        if date_match and budget.period_start is None:
            budget.period_start = mmddyyyy_to_iso(date_match.group("start"))
            budget.period_end = mmddyyyy_to_iso(date_match.group("end"))
            continue

        # High-level sections.
        if line == "PERSONNEL":
            section = "PERSONNEL"
            personnel_subsection = "salary"
            current_category = None
            continue
        if line.startswith("Fringe"):
            section = "PERSONNEL"
            personnel_subsection = "fringe"
            current_category = None
            continue
        if line == "NON-PERSONNEL":
            section = "NON_PERSONNEL"
            personnel_subsection = None
            current_category = None
            continue
        if line == "INDIRECT COSTS":
            section = "INDIRECT"
            personnel_subsection = None
            current_category = None
            continue
        if line == "TOTALS":
            section = "TOTALS"
            personnel_subsection = None
            current_category = None
            continue

        label, amounts = split_label_and_amounts(line)

        # Merge Streamlyne wrapped category labels such as:
        # "Faculty Salaries -" followed by "Academic 38,677.34 38,677.34"
        if label.endswith("-") and not amounts:
            pending_category_prefix = label
            continue

        if pending_category_prefix:
            if not label and amounts:
                continue
            possible_label = f"{pending_category_prefix} {label}".strip()
            pending_category_prefix = None
            label = possible_label

        # Effort months line belongs to the immediately previous personnel row.
        effort_match = EFFORT_RE.match(line)
        if effort_match and last_person_context:
            months = D(effort_match.group("months"))
            explicit_kind = (effort_match.group("kind") or "").lower()
            name, category, is_other = last_person_context

            if explicit_kind.startswith("acad") or explicit_kind in {"aca"}:
                month_field = "AcademicMonths"
            elif explicit_kind.startswith("sum"):
                month_field = "SummerMonths"
            elif explicit_kind.startswith("cal") or not explicit_kind:
                # Streamlyne examples sometimes show CAL even under Academic/Summer groups.
                # For RR Budget mapping, the Streamlyne personnel category is more reliable
                # than the literal CAL label beneath the row.
                month_field = CATEGORY_MONTH_FIELD.get(category, "CalendarMonths")
            else:
                month_field = CATEGORY_MONTH_FIELD.get(category, "CalendarMonths")

            add_or_update_person(
                budget=budget,
                name=name,
                category=category,
                months_delta=months,
                month_field=month_field,
                force_other=is_other,
                key_person_names=key_person_names,
            )
            continue

        if not amounts:
            continue

        amount = amounts[0]

        if section == "PERSONNEL":
            cat = canonical_category(label)
            if cat:
                current_category = cat
                last_person_context = None
                continue

            if not current_category:
                continue

            if is_section_total(label):
                last_person_context = None
                continue

            person_name = normalize_person_name(label)
            is_other = not (
                person_name in key_person_names or current_category.startswith("Faculty Salaries")
            )

            if personnel_subsection == "salary":
                add_or_update_person(
                    budget=budget,
                    name=person_name,
                    category=current_category,
                    salary_delta=amount,
                    force_other=is_other,
                    key_person_names=key_person_names,
                )
            elif personnel_subsection == "fringe":
                add_or_update_person(
                    budget=budget,
                    name=person_name,
                    category=current_category,
                    fringe_delta=amount,
                    force_other=is_other,
                    key_person_names=key_person_names,
                )

            last_person_context = (person_name, current_category, is_other)
            continue

        if section == "NON_PERSONNEL":
            if label in {"Travel", "Other Direct", "Non-Personnel Subtotal", "Calculated Direct Costs"}:
                continue

            mapped = DIRECT_COST_FIELD_MAP.get(label)
            if mapped:
                parent, field = mapped
                if parent == "Travel":
                    budget.travel_total += amount
                elif parent == "OtherDirectCosts" and field == "Other":
                    budget.other_direct_cost_lines.append((label, amount))
                else:
                    budget.other_direct_cost_fields[field] += amount
            else:
                budget.other_direct_cost_lines.append((label, amount))
            continue

        if section == "INDIRECT":
            # Example: "MTDC 43.50% 118,162.68 118,162.68"
            if "MTDC" in line.upper():
                budget.indirect_cost_type = "MTDC"
                rate_match = re.search(r"(\d+(?:\.\d+)?)%", line)
                if rate_match:
                    budget.indirect_rate = D(rate_match.group(1))
                budget.total_fa_costs = amount
            continue

        if section == "TOTALS":
            if label == "TOTAL DIRECT COSTS":
                budget.total_direct_costs = amount
            elif label in {"TOTAL F&A COSTS", "TOTAL FA COSTS"}:
                budget.total_fa_costs = amount
            elif label in {"TOTAL PROJECT COSTS", "TOTAL SPONSOR COSTS"}:
                # Prefer project costs, but sponsor and project costs are often identical.
                budget.total_project_costs = amount
            continue

    return budget


def add_text(parent: etree._Element, tag: str, value: Optional[str | decimal.Decimal | int]) -> etree._Element:
    el = etree.SubElement(parent, q_rr(tag))
    if value is None:
        el.text = ""
    elif isinstance(value, decimal.Decimal):
        el.text = fmt_money(value)
    else:
        el.text = str(value)
    return el


def add_empty(parent: etree._Element, tag: str) -> etree._Element:
    return add_text(parent, tag, "")


def split_name(full_name: str) -> tuple[str, str, str]:
    """
    Basic name splitter for RR Budget XML.
    Returns first, middle, last.
    """
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return "", "", parts[0]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def add_person_name(parent: etree._Element, full_name: str) -> None:
    name_el = etree.SubElement(parent, q_rr("Name"))
    first, middle, last = split_name(full_name)
    etree.SubElement(name_el, q_globlib("FirstName")).text = first
    if middle:
        etree.SubElement(name_el, q_globlib("MiddleName")).text = middle
    etree.SubElement(name_el, q_globlib("LastName")).text = last


def add_month_fields(parent: etree._Element, person: PersonCost) -> None:
    """
    RR_Budget_3_0 allows CalendarMonths, AcademicMonths, and SummerMonths.
    The reference XML may only show CalendarMonths, but faculty Streamlyne imports
    need AcademicMonths and SummerMonths when salary is split by category.
    """
    if person.calendar_months:
        add_text(parent, "CalendarMonths", fmt_months(person.calendar_months))
    if person.academic_months:
        add_text(parent, "AcademicMonths", fmt_months(person.academic_months))
    if person.summer_months:
        add_text(parent, "SummerMonths", fmt_months(person.summer_months))


def create_rr_budget_xml(
    budget: BudgetData,
    *,
    uei: str,
    organization_name: str,
    budget_type: str,
    key_person_roles: dict[str, str],
    budget_justification_filename: Optional[str] = None,
) -> etree._ElementTree:
    root = etree.Element(
        q_rr("RR_Budget_3_0"),
        nsmap=NSMAP,
    )
    root.set(q_rr("FormVersion"), "3.0")

    add_text(root, "SAMUEI", uei)
    add_text(root, "BudgetType", budget_type)
    add_text(root, "OrganizationName", organization_name)

    year_el = etree.SubElement(root, q_rr("BudgetYear"))
    add_text(year_el, "BudgetPeriodStartDate", budget.period_start or "")
    add_text(year_el, "BudgetPeriodEndDate", budget.period_end or "")

    # Senior / Key Persons
    key_persons_el = etree.SubElement(year_el, q_rr("KeyPersons"))

    total_key_funds = ZERO
    for name in sorted(budget.people_by_name.keys()):
        person = budget.people_by_name[name]
        kp_el = etree.SubElement(key_persons_el, q_rr("KeyPerson"))
        add_person_name(kp_el, name)
        add_text(kp_el, "ProjectRole", key_person_roles.get(name, "Senior/Key Person"))
        add_month_fields(kp_el, person)
        add_text(kp_el, "RequestedSalary", person.salary)
        add_text(kp_el, "FringeBenefits", person.fringe)
        add_text(kp_el, "FundsRequested", person.total())
        total_key_funds += person.total()

    add_text(key_persons_el, "TotalFundForKeyPersons", total_key_funds)

    # Other Personnel
    other_personnel_el = etree.SubElement(year_el, q_rr("OtherPersonnel"))
    total_other_personnel_funds = ZERO
    total_other_personnel_count = 0

    bucket_order = [
        "PostDocAssociates",
        "GraduateStudents",
        "UndergraduateStudents",
        "SecretarialClerical",
        "Other",
    ]

    for bucket in bucket_order:
        people = budget.other_personnel.get(bucket, [])
        if not people:
            continue

        bucket_el = etree.SubElement(other_personnel_el, q_rr(bucket))

        # RR Budget other personnel buckets are aggregate rows, not person-by-person rows.
        count = len(people)
        salary = sum((p.salary for p in people), ZERO)
        fringe = sum((p.fringe for p in people), ZERO)
        funds = salary + fringe
        calendar_months = sum((p.calendar_months for p in people), ZERO)
        academic_months = sum((p.academic_months for p in people), ZERO)
        summer_months = sum((p.summer_months for p in people), ZERO)

        if bucket == "PostDocAssociates":
            role = "Post Doctoral Associates"
        elif bucket == "GraduateStudents":
            role = "Graduate Students"
        elif bucket == "UndergraduateStudents":
            role = "Undergraduate Students"
        elif bucket == "SecretarialClerical":
            role = "Secretarial/Clerical"
        else:
            # If multiple different "Other" roles exist, summarize conservatively.
            role_names = sorted({p.category for p in people})
            role = "; ".join(role_names)[:100]

        add_text(bucket_el, "NumberOfPersonnel", count)
        add_text(bucket_el, "ProjectRole", role)

        pseudo = PersonCost(name=role, category=role)
        pseudo.calendar_months = calendar_months
        pseudo.academic_months = academic_months
        pseudo.summer_months = summer_months
        add_month_fields(bucket_el, pseudo)

        add_text(bucket_el, "RequestedSalary", salary)
        add_text(bucket_el, "FringeBenefits", fringe)
        add_text(bucket_el, "FundsRequested", funds)

        total_other_personnel_count += count
        total_other_personnel_funds += funds

    # Include a blank Other node if no Other bucket exists, matching many Grants.gov exports.
    if "Other" not in budget.other_personnel:
        blank_other = etree.SubElement(other_personnel_el, q_rr("Other"))
        add_empty(blank_other, "NumberOfPersonnel")
        add_empty(blank_other, "ProjectRole")
        add_empty(blank_other, "RequestedSalary")
        add_empty(blank_other, "FringeBenefits")
        add_empty(blank_other, "FundsRequested")

    add_text(other_personnel_el, "OtherPersonnelTotalNumber", total_other_personnel_count)
    add_text(other_personnel_el, "TotalOtherPersonnelFund", total_other_personnel_funds)

    total_compensation = total_key_funds + total_other_personnel_funds
    add_text(year_el, "TotalCompensation", total_compensation)

    # Equipment: empty block.
    equipment_el = etree.SubElement(year_el, q_rr("Equipment"))
    equipment_list_el = etree.SubElement(equipment_el, q_rr("EquipmentList"))
    add_empty(equipment_list_el, "EquipmentItem")
    add_empty(equipment_list_el, "FundsRequested")
    add_empty(equipment_el, "TotalFund")

    # Travel.
    travel_el = etree.SubElement(year_el, q_rr("Travel"))
    if budget.travel_total:
        add_text(travel_el, "TotalTravelCost", budget.travel_total)
    else:
        add_empty(travel_el, "TotalTravelCost")

    # Participant/Trainee support: empty block unless you extend the parser.
    pts_el = etree.SubElement(year_el, q_rr("ParticipantTraineeSupportCosts"))
    pts_other = etree.SubElement(pts_el, q_rr("Other"))
    add_empty(pts_other, "Description")
    add_empty(pts_other, "Cost")
    add_empty(pts_el, "TotalCost")

    # Other Direct Costs.
    odc_el = etree.SubElement(year_el, q_rr("OtherDirectCosts"))

    odc_total = ZERO
    odc_summary_for_cumulative: dict[str, decimal.Decimal] = defaultdict(lambda: ZERO)

    known_odc_fields = [
        "MaterialsSupplies",
        "PublicationCosts",
        "ConsultantServices",
        "ADPComputerServices",
        "SubawardsConsortiumContractualCosts",
        "EquipmentFacilityRentalUserFees",
        "AlterationsRenovations",
    ]

    for field in known_odc_fields:
        value = budget.other_direct_cost_fields.get(field, ZERO)
        if value:
            add_text(odc_el, field, value)
            odc_total += value
            odc_summary_for_cumulative[field] += value

    # Put remaining direct cost lines into OtherDirectCost1..10.
    other_lines = list(budget.other_direct_cost_lines)

    for idx in range(1, 11):
        node = etree.SubElement(odc_el, q_rr(f"OtherDirectCost{idx}"))
        if idx <= len(other_lines):
            description, cost = other_lines[idx - 1]
            add_text(node, "Description", description)
            add_text(node, "Cost", cost)
            odc_total += cost
            odc_summary_for_cumulative[f"Other{idx}"] += cost
        else:
            add_empty(node, "Description")
            add_empty(node, "Cost")

    add_text(odc_el, "TotalOtherDirectCost", odc_total)

    direct_costs = budget.total_direct_costs or (total_compensation + budget.travel_total + odc_total)
    add_text(year_el, "DirectCosts", direct_costs)

    # Indirect Costs.
    indirect_el = etree.SubElement(year_el, q_rr("IndirectCosts"))
    indirect_cost_el = etree.SubElement(indirect_el, q_rr("IndirectCost"))

    cost_type = budget.indirect_cost_type
    if budget.indirect_rate is not None:
        cost_type = f"{budget.indirect_cost_type} {budget.indirect_rate}%"

    add_text(indirect_cost_el, "CostType", cost_type)
    add_text(indirect_cost_el, "FundRequested", budget.total_fa_costs)
    add_text(indirect_el, "TotalIndirectCosts", budget.total_fa_costs)

    total_costs = budget.total_project_costs or (direct_costs + budget.total_fa_costs)
    add_text(year_el, "TotalCosts", total_costs)
    add_text(year_el, "TotalCostsFee", total_costs)

    # Optional budget justification attachment stub.
    # This does NOT embed the PDF. Grants.gov package handling is separate.
    if budget_justification_filename:
        attach_el = etree.SubElement(root, q_rr("BudgetJustificationAttachment"))
        etree.SubElement(attach_el, q_att("FileName")).text = budget_justification_filename
        etree.SubElement(attach_el, q_att("MimeType")).text = "application/pdf"
        file_loc = etree.SubElement(attach_el, q_att("FileLocation"))
        file_loc.set(f"{{{NS_ATT}}}href", budget_justification_filename)
        hash_el = etree.SubElement(attach_el, q_glob("HashValue"))
        hash_el.set(f"{{{NS_GLOB}}}hashAlgorithm", "")

    # Budget Summary / cumulative fields.
    summary_el = etree.SubElement(root, q_rr("BudgetSummary"))
    add_text(summary_el, "CumulativeTotalFundsRequestedSeniorKeyPerson", total_key_funds)
    add_text(summary_el, "CumulativeTotalFundsRequestedOtherPersonnel", total_other_personnel_funds)
    add_text(summary_el, "CumulativeTotalNoOtherPersonnel", total_other_personnel_count)
    add_text(summary_el, "CumulativeTotalFundsRequestedPersonnel", total_compensation)

    if budget.travel_total:
        add_text(summary_el, "CumulativeTotalTravel", budget.travel_total)

    add_text(summary_el, "CumulativeTotalFundsRequestedOtherDirectCosts", odc_total)

    if odc_summary_for_cumulative.get("MaterialsSupplies"):
        add_text(summary_el, "CumulativeMaterialAndSupplies", odc_summary_for_cumulative["MaterialsSupplies"])
    if odc_summary_for_cumulative.get("PublicationCosts"):
        add_text(summary_el, "CumulativePublicationCosts", odc_summary_for_cumulative["PublicationCosts"])
    if odc_summary_for_cumulative.get("ConsultantServices"):
        add_text(summary_el, "CumulativeConsultantServices", odc_summary_for_cumulative["ConsultantServices"])
    if odc_summary_for_cumulative.get("ADPComputerServices"):
        add_text(summary_el, "CumulativeADPComputerServices", odc_summary_for_cumulative["ADPComputerServices"])
    if odc_summary_for_cumulative.get("SubawardsConsortiumContractualCosts"):
        add_text(
            summary_el,
            "CumulativeSubawardConsortiumContractualCosts",
            odc_summary_for_cumulative["SubawardsConsortiumContractualCosts"],
        )

    for idx in range(1, 11):
        key = f"Other{idx}"
        if odc_summary_for_cumulative.get(key):
            add_text(summary_el, f"CumulativeOther{idx}DirectCost", odc_summary_for_cumulative[key])

    add_text(summary_el, "CumulativeTotalFundsRequestedDirectCosts", direct_costs)
    add_text(summary_el, "CumulativeTotalFundsRequestedIndirectCost", budget.total_fa_costs)
    add_text(summary_el, "CumulativeTotalFundsRequestedDirectIndirectCosts", total_costs)
    add_text(summary_el, "CumulativeTotalCostsFee", total_costs)

    return etree.ElementTree(root)


def parse_key_person_args(values: list[str]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(
                f"Invalid --key-person value {value!r}. Use format: 'Full Name=Project Role'"
            )
        name, role = value.split("=", 1)
        name = normalize_person_name(name)
        role = role.strip()
        if not name or not role:
            raise ValueError(
                f"Invalid --key-person value {value!r}. Use format: 'Full Name=Project Role'"
            )
        roles[name] = role
    return roles


def print_parse_report(budget: BudgetData, key_person_roles: dict[str, str]) -> None:
    print("\nParsed budget summary")
    print("=====================")
    print(f"Period: {budget.period_start} to {budget.period_end}")
    print(f"PI from PDF: {budget.pi_name or '(not found)'}")
    print(f"Sponsor: {budget.sponsor_name or '(not found)'}")
    print()

    print("Senior/Key Persons")
    print("------------------")
    for name, p in sorted(budget.people_by_name.items()):
        role = key_person_roles.get(name, "Senior/Key Person")
        print(
            f"{name} | {role} | "
            f"CAL={fmt_months(p.calendar_months) or '0.00'} "
            f"ACAD={fmt_months(p.academic_months) or '0.00'} "
            f"SUM={fmt_months(p.summer_months) or '0.00'} | "
            f"Salary={fmt_money(p.salary)} Fringe={fmt_money(p.fringe)} Funds={fmt_money(p.total())}"
        )

    print("\nOther Personnel")
    print("---------------")
    for bucket, people in budget.other_personnel.items():
        for p in people:
            print(
                f"{bucket}: {p.name} | "
                f"CAL={fmt_months(p.calendar_months) or '0.00'} "
                f"ACAD={fmt_months(p.academic_months) or '0.00'} "
                f"SUM={fmt_months(p.summer_months) or '0.00'} | "
                f"Salary={fmt_money(p.salary)} Fringe={fmt_money(p.fringe)} Funds={fmt_money(p.total())}"
            )

    print("\nTotals")
    print("------")
    print(f"Travel: {fmt_money(budget.travel_total)}")
    print(f"Direct Costs: {fmt_money(budget.total_direct_costs)}")
    print(f"F&A Costs: {fmt_money(budget.total_fa_costs)}")
    print(f"Project Costs: {fmt_money(budget.total_project_costs)}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a Streamlyne Budget Summary PDF to Grants.gov RR_Budget_3_0 XML."
    )
    parser.add_argument("input_pdf", type=Path, help="Path to Streamlyne Budget Page Summary PDF.")
    parser.add_argument("output_xml", type=Path, help="Path for generated RR_Budget_3_0 XML.")
    parser.add_argument("--uei", required=True, help="SAM.gov UEI for the organization.")
    parser.add_argument("--organization-name", required=True, help="Organization name.")
    parser.add_argument(
        "--budget-type",
        default="Project",
        choices=["Project", "Subaward/Consortium"],
        help="RR Budget type. Default: Project.",
    )
    parser.add_argument(
        "--pi-name",
        help="Optional PI name. Used only if no --key-person roles are supplied.",
    )
    parser.add_argument(
        "--key-person",
        action="append",
        default=[],
        help="Senior/key person mapping in the format 'Full Name=Project Role'. May be repeated.",
    )
    parser.add_argument(
        "--budget-justification-filename",
        help="Optional budget justification PDF filename to reference in the XML attachment block. "
             "This does not embed the file.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Suppress parse report printed to stdout.",
    )

    args = parser.parse_args()

    if not args.input_pdf.exists():
        print(f"ERROR: input PDF does not exist: {args.input_pdf}", file=sys.stderr)
        return 2

    try:
        key_person_roles = parse_key_person_args(args.key_person)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # If no explicit --key-person was supplied, use --pi-name as PD/PI.
    if not key_person_roles and args.pi_name:
        key_person_roles[normalize_person_name(args.pi_name)] = "PD/PI"

    key_person_names = set(key_person_roles.keys())

    lines = extract_lines(args.input_pdf)
    budget = parse_budget_pdf(lines, key_person_names)

    # If the user supplied key-person roles but one of those people only appeared in a
    # non-faculty category, promote them from OtherPersonnel into KeyPersons.
    for bucket, people in list(budget.other_personnel.items()):
        remaining = []
        for p in people:
            if p.name in key_person_names:
                if p.name not in budget.people_by_name:
                    budget.people_by_name[p.name] = copy.deepcopy(p)
                else:
                    dest = budget.people_by_name[p.name]
                    dest.salary += p.salary
                    dest.fringe += p.fringe
                    dest.calendar_months += p.calendar_months
                    dest.academic_months += p.academic_months
                    dest.summer_months += p.summer_months
            else:
                remaining.append(p)
        budget.other_personnel[bucket] = remaining

    if not budget.period_start or not budget.period_end:
        print("ERROR: Could not detect budget period date range from PDF.", file=sys.stderr)
        return 3

    tree = create_rr_budget_xml(
        budget,
        uei=args.uei,
        organization_name=args.organization_name,
        budget_type=args.budget_type,
        key_person_roles=key_person_roles,
        budget_justification_filename=args.budget_justification_filename,
    )

    args.output_xml.parent.mkdir(parents=True, exist_ok=True)
    tree.write(
        str(args.output_xml),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
    )

    if not args.no_report:
        print_parse_report(budget, key_person_roles)

    print(f"Saved XML: {args.output_xml}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
