"""
Playwright automation: attach to a user-launched Chrome session and fill the
Grants.gov Workspace R&R Budget webform from a budget_manifest.json.

Prerequisites:
  1. Launch Chrome with remote debugging:
       python3 run.py ui → click 'Launch Chrome (debug)'
  2. Log into Grants.gov, open the Workspace, navigate to the R&R Budget form.
  3. Run this script.

Usage:
  python automate_budget.py [--manifest review/budget_manifest.json] [--dry-run]
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDIT_DIR = BASE / "audit"
SS_DIR    = AUDIT_DIR / "budget_screenshots"
LOG_FILE  = AUDIT_DIR / "run_log.jsonl"

CDP_URL            = "http://127.0.0.1:9222"
IFRAME_SRC_PATTERN = "RR_Budget_3_0"  # matches both main (_V3_0) and subaward (_A_V3_0)
MODAL_ID           = "seniorKeyPersonDetail"


def _load_manifest(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def _fill_field(frame, selector: str, value: str, dry_run: bool) -> str | None:
    """Fill a text/number input field. Returns an error string or None."""
    if not value:
        return None
    if dry_run:
        return None
    try:
        el = frame.wait_for_selector(selector, timeout=5000)
        tag = el.evaluate("el => el.tagName")
        if tag == "SELECT":
            frame.select_option(selector, label=value)
        else:
            el.fill(value)
        return None
    except Exception as exc:
        return str(exc)


def _set_field(frame, selector: str, value: str, dry_run: bool) -> str | None:
    value = value or ""
    if dry_run:
        return None
    try:
        el = frame.wait_for_selector(selector, timeout=5000)
        tag = el.evaluate("el => el.tagName")
        if tag == "SELECT":
            frame.select_option(selector, label=value)
        else:
            el.fill(value)
        return None
    except Exception as exc:
        return str(exc)


def _count_rows(frame, selector_template: str, max_rows: int, start: int = 1) -> int:
    count = 0
    for idx in range(start, max_rows + 1):
        try:
            loc = frame.locator(selector_template.format(N=idx))
            if loc.count() > 0 and loc.first.is_visible():
                count = idx
        except Exception:
            continue
    return count


def _click_first_button_by_text(frame, snippets: list[str]) -> bool:
    for snippet in snippets:
        try:
            btn = frame.locator(f"button:has-text('{snippet}')").first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                return True
        except Exception:
            continue
    try:
        for btn in frame.query_selector_all("button"):
            try:
                text = btn.inner_text()
            except Exception:
                continue
            if any(snippet in text for snippet in snippets):
                btn.click()
                return True
    except Exception:
        pass
    return False


def _ensure_budget_period_exists(frame, period_idx: int, dry_run: bool) -> str | None:
    period_marker_selectors = [
        f"#budgetPeriodStartDate{period_idx}",
        f"#keyPersonAdd{period_idx}",
        f"#listD{period_idx}_1",
    ]

    for selector in period_marker_selectors:
        try:
            if frame.locator(selector).count() > 0:
                return None
        except Exception:
            continue

    if dry_run:
        print(f"  DRY-RUN: would add budget periods until Period {period_idx} exists")
        return None

    add_selectors = [
        "button[data-bind*='addBudgetPeriod']",
        "button:has-text('Add Period')",
    ]

    for _ in range(1, 6):
        created = False
        for selector in period_marker_selectors:
            try:
                if frame.locator(selector).count() > 0:
                    return None
            except Exception:
                continue

        for sel in add_selectors:
            try:
                btn = frame.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    created = True
                    break
            except Exception:
                continue

        if not created:
            try:
                for btn in frame.query_selector_all("button"):
                    try:
                        if "Add Period" in btn.inner_text():
                            btn.click()
                            created = True
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        if not created:
            return f"Add Period button not found for Period {period_idx}"

        time.sleep(0.5)
        for selector in period_marker_selectors:
            try:
                frame.wait_for_selector(selector, timeout=5000)
                return None
            except Exception:
                continue

    return f"Period {period_idx} did not appear after clicking Add Period"


# ─────────────────────────────────────────────────────────────────────────────
# Section A — Senior Key Persons (add via modal)
# ─────────────────────────────────────────────────────────────────────────────

def _open_modal(frame, add_button_sel: str, dry_run: bool) -> bool:
    """Click the Add button and wait for the modal to open."""
    if dry_run:
        print(f"    DRY-RUN: would click '{add_button_sel}'")
        return True
    try:
        frame.click(add_button_sel)
        frame.wait_for_selector(f"#{MODAL_ID}.in, #{MODAL_ID}[style*='display: block']",
                                timeout=8000)
        # Brief wait for modal animation
        time.sleep(0.4)
        return True
    except Exception as exc:
        print(f"    WARNING: could not open modal via '{add_button_sel}': {exc}")
        return False


def _close_modal(frame, dry_run: bool) -> None:
    """Click the modal's Save button and wait for it to close."""
    if dry_run:
        print("    DRY-RUN: would click modal Save")
        return
    try:
        frame.locator(".modal-footer .btn-primary").first.click()
        # Wait for modal to disappear
        frame.wait_for_selector(
            f"#{MODAL_ID}:not(.in)",
            timeout=8000,
        )
        time.sleep(0.3)
    except Exception as exc:
        print(f"    WARNING: error closing modal: {exc}")


def _fill_modal(frame, person: dict, dry_run: bool) -> dict:
    """Fill all fields in the Senior Key Person modal."""
    modal_fields = {
        "#firstName":       person.get("first_name", ""),
        "#lastName":        person.get("last_name", ""),
        "#projectRole":     person.get("project_role", ""),
        "#baseSalary":      person.get("base_salary", ""),
        "#calendarMonths":  person.get("calendar_months", ""),
        "#academicMonths":  person.get("academic_months", ""),
        "#summerMonths":    person.get("summer_months", ""),
        "#requestedSalary": person.get("requested_salary", ""),
        "#fringeBenefits":  person.get("fringe_benefits", ""),
    }
    filled = {}
    skipped = {}
    for sel, val in modal_fields.items():
        if not val:
            continue
        err = _fill_field(frame, sel, val, dry_run)
        if err:
            skipped[sel] = err
        else:
            filled[sel] = val
    return {"filled": filled, "skipped": skipped}


def _fill_section_a_row(frame, period_idx: int, row_idx: int, person: dict, dry_run: bool) -> dict:
    filled = {}
    skipped = {}
    fields = {
        f"#baseSalaryA{period_idx}_{row_idx}": person.get("base_salary", ""),
        f"#calendarMonthsA{period_idx}_{row_idx}": person.get("calendar_months", ""),
        f"#academicMonthsA{period_idx}_{row_idx}": person.get("academic_months", ""),
        f"#summerMonthsA{period_idx}_{row_idx}": person.get("summer_months", ""),
        f"#requestedSalaryA{period_idx}_{row_idx}": person.get("requested_salary", ""),
        f"#fringeBenefitsA{period_idx}_{row_idx}": person.get("fringe_benefits", ""),
    }
    for selector, value in fields.items():
        err = _set_field(frame, selector, value, dry_run)
        if err:
            skipped[selector] = err
        else:
            filled[selector] = value
    return {"filled": filled, "skipped": skipped}


def _clear_section_a_row(frame, period_idx: int, row_idx: int, dry_run: bool) -> dict:
    return _fill_section_a_row(frame, period_idx, row_idx, {}, dry_run)


def _delete_section_a_row(frame, period_idx: int, row_idx: int, dry_run: bool) -> str | None:
    if row_idx <= 1:
        return None
    if dry_run:
        return None
    selector = f"#deleteSeniorkeyperson{period_idx}_{row_idx}"
    try:
        btn = frame.locator(selector)
        if btn.count() == 0:
            return None
        btn.first.click()
        time.sleep(0.2)
        return None
    except Exception as exc:
        return str(exc)


def _add_key_persons(frame, period_idx: int, persons: list[dict], dry_run: bool) -> list[dict]:
    logs = []
    add_btn = f"#keyPersonAdd{period_idx}"
    existing_rows = _count_rows(frame, f"#requestedSalaryA{period_idx}_{{N}}", 10)

    if period_idx > 1 and existing_rows < len(persons):
        for _ in range(existing_rows + 1, len(persons) + 1):
            opened = _open_modal(frame, add_btn, dry_run)
            if not opened:
                logs.append({"status": "modal open failed", "mode": "add-slot"})
                break
            _close_modal(frame, dry_run)
            time.sleep(0.1)
        existing_rows = _count_rows(frame, f"#requestedSalaryA{period_idx}_{{N}}", 10)

    for row_idx, person in enumerate(persons, 1):
        name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
        print(f"      + Key Person: {name} ({person.get('project_role', '')})")

        if period_idx == 1:
            opened = _open_modal(frame, add_btn, dry_run)
            if not opened:
                logs.append({"person": name, "status": "modal open failed", "mode": "add", "row_index": row_idx})
                continue
            result = _fill_modal(frame, person, dry_run)
            _close_modal(frame, dry_run)
            mode = "add"
        else:
            result = _fill_section_a_row(frame, period_idx, row_idx, person, dry_run)
            mode = "row-fill"

        print(f"        filled={len(result['filled'])}  skipped={len(result['skipped'])}")
        if result["skipped"]:
            for s, e in result["skipped"].items():
                print(f"        skip {s}: {e}")
        logs.append({
            "person": name,
            "fields_filled": len(result["filled"]),
            "fields_skipped": result["skipped"],
            "mode": mode,
            "row_index": row_idx,
        })
        time.sleep(0.1)

    if period_idx > 1 and existing_rows > len(persons):
        for row_idx in range(existing_rows, len(persons), -1):
            clear_result = _clear_section_a_row(frame, period_idx, row_idx, dry_run)
            delete_status = _delete_section_a_row(frame, period_idx, row_idx, dry_run)
            logs.append({
                "row_index": row_idx,
                "mode": "delete-extra",
                "fields_skipped": clear_result["skipped"],
                "delete_status": delete_status,
            })

    return logs


# ─────────────────────────────────────────────────────────────────────────────
# Section B — Other Personnel (pre-defined rows, fill by index)
# ─────────────────────────────────────────────────────────────────────────────

# Standard row index mapping (1-based) for pre-defined Section B categories
_SECTION_B_ROW = {
    "post_doc_associates":    1,
    "graduate_students":      2,
    "undergraduate_students": 3,
    "secretarial_clerical":   4,
}


def _fill_section_b(frame, period_idx: int, section_b: dict, dry_run: bool) -> dict:
    P = period_idx
    filled = {}
    skipped = {}

    def _fill_row(row_idx: int, row: dict) -> None:
        if row_idx >= 5:
            role_fid = f"listB{P}_{row_idx}"
            role = row.get("project_role", "")
            err = _set_field(frame, f"#{role_fid}", role, dry_run)
            if err:
                skipped[role_fid] = err
            else:
                filled[role_fid] = role

        fields = {
            f"numberOfPersonnel{P}_{row_idx}": row.get("number_of_personnel", ""),
            f"calendarMonthsB{P}_{row_idx}":   row.get("calendar_months", ""),
            f"academicMonthsB{P}_{row_idx}":   row.get("academic_months", ""),
            f"summerMonthsB{P}_{row_idx}":     row.get("summer_months", ""),
            f"requestedSalaryB{P}_{row_idx}":  row.get("requested_salary", ""),
            f"fringeBenefitsB{P}_{row_idx}":   row.get("fringe_benefits", ""),
        }
        for fid, val in fields.items():
            err = _set_field(frame, f"#{fid}", val, dry_run)
            if err:
                skipped[fid] = err
            else:
                filled[fid] = val

    for key, row_idx in _SECTION_B_ROW.items():
        _fill_row(row_idx, section_b.get(key, {}))

    # Dynamically added "Other" rows
    other_rows = section_b.get("other_personnel", [])
    existing_dynamic = _count_rows(frame, f"#numberOfPersonnel{P}_{{N}}", 10, start=5)
    needed_dynamic = 4 + len(other_rows)
    for target_idx in range(max(existing_dynamic + 1, 5), needed_dynamic + 1):
        if dry_run:
            print(f"      DRY-RUN: would add Other Personnel row {target_idx}")
            continue
        if not _click_first_button_by_text(frame, ["Add Additional Other Personnel"]):
            skipped[f"other_row_{target_idx}"] = "Add button not found"
            continue
        try:
            frame.wait_for_selector(f"#numberOfPersonnel{P}_{target_idx}", timeout=5000)
        except Exception as exc:
            skipped[f"other_row_{target_idx}"] = str(exc)

    for idx, row in enumerate(other_rows, 5):
        _fill_row(idx, row)

    for row_idx in range(5 + len(other_rows), max(existing_dynamic, needed_dynamic) + 1):
        _fill_row(row_idx, {})

    return {"filled": filled, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────────────
# Section C — Equipment
# ─────────────────────────────────────────────────────────────────────────────

def _fill_section_c(frame, period_idx: int, section_c: dict, dry_run: bool) -> dict:
    P = period_idx
    items = section_c.get("items", [])
    filled = {}
    skipped = {}

    for i, item in enumerate(items, 1):
        if i > 1 and i > _count_rows(frame, f"#equipmentItem{P}_{{N}}", 10):
            if dry_run:
                print(f"      DRY-RUN: would add equipment row {i}")
            else:
                if not _click_first_button_by_text(frame, ["Add Additional Equipment"]):
                    skipped[f"equip_add_{i}"] = "Add button not found"
                    continue
                try:
                    frame.wait_for_selector(f"#equipmentItem{P}_{i}", timeout=5000)
                except Exception as exc:
                    skipped[f"equip_add_{i}"] = str(exc)
                    continue

        for fid, val in [
            (f"equipmentItem{P}_{i}", item.get("item", "")),
            (f"fundsRequestedC{P}_{i}", item.get("funds_requested", "")),
        ]:
            err = _set_field(frame, f"#{fid}", val, dry_run)
            if err:
                skipped[fid] = err
            else:
                filled[fid] = val

    existing_rows = _count_rows(frame, f"#equipmentItem{P}_{{N}}", 10)
    for i in range(len(items) + 1, existing_rows + 1):
        for fid in [f"equipmentItem{P}_{i}", f"fundsRequestedC{P}_{i}"]:
            err = _set_field(frame, f"#{fid}", "", dry_run)
            if err:
                skipped[fid] = err

    return {"filled": filled, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────────────
# Section D — Travel
# ─────────────────────────────────────────────────────────────────────────────

def _fill_section_d(frame, period_idx: int, section_d: dict, dry_run: bool) -> dict:
    P = period_idx
    filled = {}
    skipped = {}

    row_fields = {
        f"listD{P}_1": section_d.get("domestic_travel_cost", "") or section_d.get("total_travel_cost", ""),
        f"listD{P}_2": section_d.get("foreign_travel_cost", ""),
    }
    for fid, val in row_fields.items():
        err = _set_field(frame, f"#{fid}", val, dry_run)
        if err:
            skipped[fid] = err
        else:
            filled[fid] = val

    return {"filled": filled, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────────────
# Section F — Other Direct Costs
# ─────────────────────────────────────────────────────────────────────────────

def _fill_section_f(frame, period_idx: int, section_f: dict, dry_run: bool) -> dict:
    P = period_idx
    filled = {}
    skipped = {}

    fixed_rows = {
        1: section_f.get("materials_supplies", ""),
        2: section_f.get("publication_costs", ""),
        3: section_f.get("consultant_services", ""),
        4: section_f.get("adp_computer_services", ""),
        5: section_f.get("subawards_consortium_contractual_costs", ""),
        6: section_f.get("equipment_facility_rental_user_fees", ""),
        7: section_f.get("alterations_renovations", ""),
    }
    for row_idx, value in fixed_rows.items():
        fid = f"fundsRequestedF{P}_{row_idx}"
        err = _set_field(frame, f"#{fid}", value, dry_run)
        if err:
            skipped[fid] = err
        else:
            filled[fid] = value

    # Other items → rows 8+ (user-defined description + cost)
    other_items = section_f.get("other_items", [])
    next_row = 8  # rows 2-7 are standard fixed categories (Publication, Consultant, etc.)
    for item in other_items:
        desc = item.get("description", "")
        cost = item.get("cost", "")
        desc_fid = f"listF{P}_{next_row}"
        cost_fid = f"fundsRequestedF{P}_{next_row}"
        for fid, val in [(desc_fid, desc), (cost_fid, cost)]:
            err = _set_field(frame, f"#{fid}", val, dry_run)
            if err:
                skipped[fid] = err
            else:
                filled[fid] = val
        next_row += 1

    for row_idx in range(next_row, 18):
        for fid in [f"listF{P}_{row_idx}", f"fundsRequestedF{P}_{row_idx}"]:
            err = _set_field(frame, f"#{fid}", "", dry_run)
            if err:
                skipped[fid] = err

    return {"filled": filled, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────────────
# Section H — Indirect Costs
# ─────────────────────────────────────────────────────────────────────────────

def _fill_section_h(frame, period_idx: int, section_h: dict, dry_run: bool) -> dict:
    P = period_idx
    costs = section_h.get("indirect_costs", [])
    cog   = section_h.get("cognizant_agency", "")
    filled = {}
    skipped = {}

    for i, cost in enumerate(costs, 1):
        if i > 1 and i > _count_rows(frame, f"#indirectCostType{P}_{{N}}", 4):
            if dry_run:
                print(f"      DRY-RUN: would add indirect cost row {i}")
            else:
                if not _click_first_button_by_text(frame, ["Add Additional Indirect Cost"]):
                    skipped[f"ic_add_{i}"] = "Add button not found"
                    continue
                try:
                    frame.wait_for_selector(f"#indirectCostType{P}_{i}", timeout=5000)
                except Exception as exc:
                    skipped[f"ic_add_{i}"] = str(exc)
                    continue

        row_fields = {
            f"indirectCostType{P}_{i}": cost.get("cost_type", ""),
            f"indirectCostRate{P}_{i}": cost.get("rate", ""),
            f"indirectCostBase{P}_{i}": cost.get("base", ""),
            f"fundsRequestedH{P}_{i}":  cost.get("fund_requested", ""),
        }
        for fid, val in row_fields.items():
            err = _set_field(frame, f"#{fid}", val, dry_run)
            if err:
                skipped[fid] = err
            else:
                filled[fid] = val

    existing_rows = _count_rows(frame, f"#indirectCostType{P}_{{N}}", 4)
    for i in range(len(costs) + 1, existing_rows + 1):
        for fid in [
            f"indirectCostType{P}_{i}",
            f"indirectCostRate{P}_{i}",
            f"indirectCostBase{P}_{i}",
            f"fundsRequestedH{P}_{i}",
        ]:
            err = _set_field(frame, f"#{fid}", "", dry_run)
            if err:
                skipped[fid] = err

    # Cognizant Federal Agency textarea
    fid = f"cognizantFederalAgency{P}"
    err = _set_field(frame, f"#{fid}", cog, dry_run)
    if err:
        skipped[fid] = err
    else:
        filled[fid] = cog

    return {"filled": filled, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────────────
# Budget Justification file attachment
# ─────────────────────────────────────────────────────────────────────────────

def _attach_justification(frame, path_str: str | None, dry_run: bool) -> str | None:
    if not path_str:
        return None
    p = BASE / path_str
    if not p.exists():
        return f"File not found: {p}"
    if dry_run:
        return f"DRY-RUN: would upload {p.name}"
    try:
        frame.locator("#budgetJustificationFile").set_input_files(str(p))
        return f"uploaded {p.name}"
    except Exception as exc:
        return f"ERROR: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Save form
# ─────────────────────────────────────────────────────────────────────────────

def _save_form(frame, page, dry_run: bool) -> str:
    if dry_run:
        return "DRY-RUN: would click save"
    try:
        frame.locator("#footerSaveUpload").click()
        page.wait_for_load_state("networkidle", timeout=20000)
        err_visible = frame.locator("#errors.errormessage").is_visible()
        if err_visible:
            err_text = frame.locator("#errors.errormessage").inner_text()
            return f"save error: {err_text[:120]}"
        return "saved"
    except Exception as exc:
        return f"save error: {exc}"


def _click_ok_confirmation(frame, page, dry_run: bool) -> str | None:
    if dry_run:
        return "DRY-RUN: would click OK if present"
    selectors = [
        "button:has-text('OK')", "button:has-text('Ok')",
        "input[value='OK']", "input[value='Ok']",
        ".ui-dialog-buttonset button", "[role='dialog'] button",
    ]
    for ctx_name, ctx in [("iframe", frame), ("page", page)]:
        for sel in selectors:
            try:
                loc = ctx.locator(sel).first
                if loc.is_visible(timeout=1000):
                    loc.click()
                    return f"clicked OK in {ctx_name}"
            except Exception:
                continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main run
# ─────────────────────────────────────────────────────────────────────────────

def run(manifest_path: Path | None = None, dry_run: bool = False) -> None:
    manifest_path = manifest_path or (BASE / "review" / "budget_manifest.json")
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}. Run normalize-budget first.")
        sys.exit(1)

    entries = _load_manifest(manifest_path)
    if not entries:
        print("Budget manifest is empty.")
        return

    SS_DIR.mkdir(parents=True, exist_ok=True)

    # Preflight Chrome check (reuse existing helper)
    sys.path.insert(0, str(BASE / "scripts"))
    import automate as kp_automate
    kp_automate._preflight_chrome()

    from playwright.sync_api import sync_playwright

    print(f"{'DRY-RUN: ' if dry_run else ''}Connecting to Chrome at {CDP_URL} …")

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            print(f"\nCould not connect: {exc}")
            sys.exit(1)

        context = browser.contexts[0]
        page = None
        for p in context.pages:
            if "grants.gov" in p.url:
                page = p
                break
        if page is None:
            print("No Grants.gov tab found.")
            for p in context.pages:
                print(f"  open tab: {p.url}")
            sys.exit(1)

        print(f"  Using tab: {page.url[:80]}")

        # Find budget form iframe
        frame = None
        for attempt in range(15):
            for f in page.frames:
                if IFRAME_SRC_PATTERN in f.url:
                    frame = f
                    break
            if frame:
                break
            time.sleep(1)

        if frame is None:
            print(f"\nCould not find iframe matching '{IFRAME_SRC_PATTERN}'.")
            print("Make sure you are on the R&R Budget form, not the Workspace overview.")
            print("Frames currently loaded:")
            for f in page.frames:
                print(f"  {f.url or '(no url)'}")
            sys.exit(1)

        print(f"  Form iframe: {frame.url[:80]}")

        if not dry_run:
            page.screenshot(path=str(SS_DIR / "000_before_all.png"))

        all_logs = []

        for entry_i, entry in enumerate(entries):
            org  = entry.get("organization", {}).get("name", f"entry #{entry_i+1}")
            just = entry.get("budget_justification", {})
            entry_periods = entry.get("periods", [])
            print(f"\n[{entry_i+1}/{len(entries)}] {org}")

            for period in entry_periods:
                P = period["period_index"]
                print(f"\n  Budget Period {P} "
                      f"({period.get('start_date','')} – {period.get('end_date','')})")

                period_log: dict = {
                    "timestamp":    datetime.now(timezone.utc).isoformat(),
                    "action":       "fill_budget_period",
                    "dry_run":      dry_run,
                    "source_pdf":   entry.get("source_pdf", ""),
                    "period_index": P,
                }

                ensure_status = _ensure_budget_period_exists(frame, P, dry_run)
                if ensure_status:
                    print(f"  WARNING: {ensure_status}")
                    period_log["period_setup"] = ensure_status
                    all_logs.append(period_log)
                    continue

                # Section A — Key Persons
                kps = period.get("section_a", {}).get("key_persons", [])
                if kps:
                    print(f"  Section A: {len(kps)} key person(s)")
                    kp_logs = _add_key_persons(frame, P, kps, dry_run)
                    period_log["section_a"] = kp_logs
                else:
                    print("  Section A: no key persons")

                # Section B — Other Personnel
                sec_b = period.get("section_b", {})
                print("  Section B: filling other personnel …")
                b_result = _fill_section_b(frame, P, sec_b, dry_run)
                print(f"    filled={len(b_result['filled'])}  skipped={len(b_result['skipped'])}")
                period_log["section_b"] = b_result

                # Section C — Equipment
                sec_c = period.get("section_c", {})
                print(f"  Section C: {len(sec_c.get('items', []))} equipment item(s) …")
                c_result = _fill_section_c(frame, P, sec_c, dry_run)
                print(f"    filled={len(c_result['filled'])}  skipped={len(c_result['skipped'])}")
                period_log["section_c"] = c_result

                # Section D — Travel
                sec_d = period.get("section_d", {})
                print("  Section D: filling travel …")
                d_result = _fill_section_d(frame, P, sec_d, dry_run)
                print(f"    filled={len(d_result['filled'])}  skipped={len(d_result['skipped'])}")
                period_log["section_d"] = d_result

                # Section F — Other Direct Costs
                sec_f = period.get("section_f", {})
                print("  Section F: filling direct costs …")
                f_result = _fill_section_f(frame, P, sec_f, dry_run)
                print(f"    filled={len(f_result['filled'])}  skipped={len(f_result['skipped'])}")
                period_log["section_f"] = f_result

                # Section H — Indirect Costs
                sec_h = period.get("section_h", {})
                print(f"  Section H: {len(sec_h.get('indirect_costs', []))} indirect cost row(s) …")
                h_result = _fill_section_h(frame, P, sec_h, dry_run)
                print(f"    filled={len(h_result['filled'])}  skipped={len(h_result['skipped'])}")
                period_log["section_h"] = h_result

                all_logs.append(period_log)

            # Budget Justification (once per source PDF, outside period loop)
            just_status = _attach_justification(frame, just.get("path"), dry_run)
            if just_status:
                print(f"\n  Budget Justification: {just_status}")
                if all_logs:
                    all_logs[-1]["justification_status"] = just_status

        # Save
        print(f"\nSaving form …")
        save_status = _save_form(frame, page, dry_run)
        print(f"  save: {save_status}")

        ok_status = _click_ok_confirmation(frame, page, dry_run)
        if ok_status:
            print(f"  confirmation: {ok_status}")
            if not dry_run:
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

        if not dry_run:
            page.screenshot(path=str(SS_DIR / "999_after_save.png"))

        # Write audit log
        with LOG_FILE.open("a") as lf:
            for log_entry in all_logs:
                log_entry["save_status"] = save_status
                log_entry["ok_confirmation"] = ok_status
                lf.write(json.dumps(log_entry) + "\n")

    print(f"\n{'DRY-RUN ' if dry_run else ''}Complete. Audit log: {LOG_FILE.relative_to(BASE)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(args.manifest, args.dry_run)
