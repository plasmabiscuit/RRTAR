"""
Playwright automation: attach to a user-launched Chrome session and add approved
Senior/Key Person entries to the Grants.gov Workspace R&R Key Person Expanded webform.

Prerequisites:
  1. Launch Chrome with remote debugging:
       google-chrome --remote-debugging-port=9222
  2. Log into Grants.gov manually.
  3. Open the correct Workspace and navigate to the R&R Senior/Key Person Expanded form.
  4. Run this script.

Usage:
  python automate.py [--manifest review/import_manifest.json] [--dry-run]
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDIT_DIR = BASE / "audit"
SS_DIR = AUDIT_DIR / "before_after_screenshots"
LOG_FILE = AUDIT_DIR / "run_log.jsonl"
SELECTOR_FILE = BASE / "config" / "selector_profile.grantsgov-rr-keyperson-4.0.json"

CDP_URL = "http://127.0.0.1:9222"  # explicit IPv4 — Chrome only binds here, not ::1
IFRAME_ID = "webformEditIFrame"
IFRAME_SRC_PATTERN = "RR_KeyPersonExpanded_4_0"
ADD_BUTTON_SEL = "#addProfile button"
PAUSE_BETWEEN_PERSONS = 2.0  # seconds

_US_STATE_MAP = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "AS": "American Samoa", "GU": "Guam", "MP": "Northern Mariana Islands",
    "PR": "Puerto Rico", "VI": "U.S. Virgin Islands",
}
_US_STATE_NAME_TO_ABBR = {name.upper(): abbr for abbr, name in _US_STATE_MAP.items()}



def _load_manifest(path: Path) -> list[dict]:
    entries = json.loads(path.read_text())
    return [e for e in entries if not e.get("exclude", False)]


def _load_selector_profile() -> dict:
    return json.loads(SELECTOR_FILE.read_text())


def _count_existing_persons(frame) -> int:
    """Count how many personFirstName{N} inputs already exist in the frame."""
    inputs = frame.query_selector_all("[id^='personFirstName']")
    return len(inputs)


def _normalize_choice(value: str) -> str:
    return "".join(ch for ch in value.upper().strip() if ch.isalnum())


def _select_with_fallbacks(frame, selector: str, value: str, field_id: str) -> None:
    if not value:
        return

    try:
        frame.select_option(selector, label=value)
        return
    except Exception:
        pass

    try:
        frame.select_option(selector, value=value)
        return
    except Exception:
        pass

    candidates = [value]
    if "State" in field_id:
        upper = value.upper().strip()
        if upper in _US_STATE_MAP:
            candidates.append(_US_STATE_MAP[upper])
        elif upper in _US_STATE_NAME_TO_ABBR:
            candidates.append(_US_STATE_NAME_TO_ABBR[upper])

    loc = frame.locator(selector)
    options = loc.locator("option")
    count = options.count()
    normalized_candidates = {_normalize_choice(candidate) for candidate in candidates if candidate}

    for idx in range(count):
        option = options.nth(idx)
        label = (option.text_content() or "").strip()
        opt_value = (option.get_attribute("value") or "").strip()
        if (
            _normalize_choice(label) in normalized_candidates
            or _normalize_choice(opt_value) in normalized_candidates
        ):
            loc.select_option(index=idx)
            return

    raise ValueError(f"no matching option for '{value}'")


def _fill_person(frame, n: int, person: dict, profile: dict, dry_run: bool) -> dict:
    """Fill all fields for the N-th (1-based) Senior/Key Person block. Returns field diff dict."""
    fields = profile["sections"]["senior_key_person_profile"]["fields"]
    filled = {}
    skipped = {}

    addr = person.get("address", {})
    field_values = {
        "Prefix":                 person.get("prefix", ""),
        "FirstName":              person.get("first_name", ""),
        "MiddleName":             person.get("middle_name", ""),
        "LastName":               person.get("last_name", ""),
        "Suffix":                 person.get("suffix", ""),
        "Title":                  person.get("title", ""),
        "Organization":           person.get("organization_name", ""),
        "Department":             person.get("department", ""),
        "Division":               person.get("division", ""),
        "Street1":                addr.get("street1", ""),
        "Street2":                addr.get("street2", ""),
        "City":                   addr.get("city", ""),
        "County":                 addr.get("county", ""),
        "State":                  addr.get("state", ""),
        "Province":               addr.get("province", ""),
        "Country":                addr.get("country", ""),
        "ZipCode":                addr.get("postal_code", ""),
        "PhoneNumber":            person.get("phone", ""),
        "FaxNumber":              person.get("fax", ""),
        "Email":                  person.get("email", ""),
        "Credential":             person.get("credential", ""),
        "ProjectRole":            person.get("project_role", ""),
        "OtherProjectRole":       person.get("other_project_role_category", ""),
        "DegreeType":             person.get("degree_type", ""),
        "DegreeYear":             person.get("degree_year", ""),
    }

    for field_def in fields:
        tmpl = field_def.get("id_template", "")
        if not tmpl or field_def["type"] == "file":
            continue

        field_id = tmpl.replace("{N}", str(n))
        # Map template key to field_values key
        key = (tmpl
               .replace("person", "")
               .replace("{N}", "")
               .strip())
        value = field_values.get(key, "")

        if not value:
            continue

        selector = f"#{field_id}"

        if dry_run:
            filled[field_id] = value
            continue

        try:
            el = frame.wait_for_selector(selector, timeout=5000)
            tag = el.evaluate("el => el.tagName")
            if tag == "SELECT":
                _select_with_fallbacks(frame, selector, value, field_id)
            else:
                el.fill(value)
            filled[field_id] = value
        except Exception as exc:
            skipped[field_id] = str(exc)

    return {"filled": filled, "skipped": skipped}


def _attach_file(frame, selector: str, file_path: str, dry_run: bool) -> str | None:
    if not file_path:
        return None
    p = BASE / file_path
    if not p.exists():
        return f"File not found: {p}"  # absolute path so the error is actionable
    if dry_run:
        return f"DRY-RUN: would upload {p.name}"
    try:
        # set_input_files works on hidden file inputs directly
        frame.locator(selector).set_input_files(str(p))
        return f"uploaded {p.name}"
    except Exception as exc:
        return f"ERROR: {exc}"


def _save_form(frame, page, dry_run: bool) -> str:
    if dry_run:
        return "DRY-RUN: would click save"
    try:
        # Confirmed selector from live form inspection: input#footerSaveUpload
        frame.locator("#footerSaveUpload").click()
        # Wait for the network to go quiet — Grants.gov does an AJAX save
        page.wait_for_load_state("networkidle", timeout=20000)
        # Check for error message
        err_visible = frame.locator("#errors.errormessage").is_visible()
        if err_visible:
            err_text = frame.locator("#errors.errormessage").inner_text()
            return f"save error from form: {err_text[:120]}"
        return "saved"
    except Exception as exc:
        return f"save error: {exc}"


def _click_ok_confirmation(frame, page, dry_run: bool) -> str | None:
    """Click an OK/confirmation button that Grants.gov shows after saving.

    Tries the iframe first, then the parent page, using several common
    label and selector patterns.
    """
    if dry_run:
        return "DRY-RUN: would click OK if present"

    selectors = [
        ("button:has-text('OK')",    "OK"),
        ("button:has-text('Ok')",    "Ok"),
        ("button:has-text('Okay')",  "Okay"),
        ("input[value='OK']",        "OK input"),
        ("input[value='Ok']",        "Ok input"),
        (".ui-dialog-buttonset button", "dialog button"),
        ("[role='dialog'] button",   "dialog role button"),
    ]

    for ctx_name, ctx in [("iframe", frame), ("page", page)]:
        for sel, label in selectors:
            try:
                loc = ctx.locator(sel).first
                if loc.is_visible(timeout=1000):
                    loc.click()
                    return f"clicked '{label}' in {ctx_name}"
            except Exception:
                continue

    return None  # no confirmation button found — that's fine


def _verify_fields(frame, n: int, expected: dict) -> list[str]:
    """Re-read filled fields and return list of discrepancies."""
    diffs = []
    for field_id, expected_val in expected.items():
        try:
            el = frame.query_selector(f"#{field_id}")
            if el is None:
                diffs.append(f"{field_id}: element not found after save")
                continue
            tag = el.evaluate("el => el.tagName")
            if tag == "SELECT":
                # Grants.gov options have empty value attrs; compare by selected text
                actual = el.evaluate(
                    "el => el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : ''"
                )
            else:
                actual = el.evaluate("el => el.value")
            if actual.strip() != expected_val.strip():
                diffs.append(f"{field_id}: expected '{expected_val}', got '{actual}'")
        except Exception as exc:
            diffs.append(f"{field_id}: read error {exc}")
    return diffs


def check_chrome() -> dict:
    """Return a diagnostic dict: port open, /json/version reachable, open tabs."""
    import socket
    import urllib.request
    import urllib.error

    result = {"port_open": False, "version": None, "tabs": [], "error": None}

    try:
        with socket.create_connection(("127.0.0.1", 9222), timeout=1):
            result["port_open"] = True
    except OSError:
        return result

    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3) as r:
            result["version"] = json.loads(r.read())
    except Exception as exc:
        result["error"] = str(exc)
        return result

    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=3) as r:
            result["tabs"] = json.loads(r.read())
    except Exception:
        pass

    return result


def _preflight_chrome() -> None:
    """Verify Chrome's debug port is open; print actionable diagnostics and exit if not."""
    diag = check_chrome()

    if diag["port_open"] and diag["version"]:
        ver = diag["version"].get("Browser", "unknown")
        tabs = len(diag["tabs"])
        print(f"  Chrome {ver}  ·  {tabs} tab(s) open")
        return

    # Not reachable — explain exactly what to do
    print()
    print("─" * 60)
    print("ERROR: Chrome remote debugging is not available on 127.0.0.1:9222")
    print()
    print("Chrome must be restarted with --remote-debugging-port=9222.")
    print("The easiest way is to close all Chrome windows, then either:")
    print()
    print("  Option A — from the terminal:")
    profile = BASE / ".chrome-debug-profile"
    print(f"    google-chrome --remote-debugging-port=9222 \\")
    print(f"      --user-data-dir={profile}")
    print()
    print("    (Chrome requires a non-default --user-data-dir to allow remote debugging.)")
    print()
    print("  Option B — click 'Launch Chrome (debug)' in the dashboard:")
    print("    python3 run.py ui")
    print()
    print("Then log into Grants.gov, open the Workspace,")
    print("navigate to the R&R Senior/Key Person Expanded form, and re-run automate.")
    print("─" * 60)
    sys.exit(1)


def run(manifest_path: Path | None = None, dry_run: bool = False) -> None:
    manifest_path = manifest_path or (BASE / "review" / "import_manifest.json")
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}. Run normalize first.")
        sys.exit(1)

    entries = _load_manifest(manifest_path)
    if not entries:
        print("No approved persons in manifest (all excluded or empty).")
        return

    profile = _load_selector_profile()
    SS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"{'DRY-RUN: ' if dry_run else ''}Connecting to Chrome at {CDP_URL} …")
    _preflight_chrome()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            print(f"\nCould not connect: {exc}")
            sys.exit(1)

        context = browser.contexts[0]

        # Find the Grants.gov tab — don't assume it's pages[0]
        page = None
        for p in context.pages:
            if "grants.gov" in p.url:
                page = p
                break
        if page is None:
            print("No Grants.gov tab found. Open the Workspace form in the debug Chrome window.")
            for p in context.pages:
                print(f"  open tab: {p.url}")
            sys.exit(1)

        print(f"  Using tab: {page.url[:80]}")

        # Wait up to 15 s for the webform iframe to appear and finish loading.
        # The iframe src contains the form name (e.g. RR_KeyPersonExpanded_4_0_V4_0.html).
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
            print("Frames currently loaded on that tab:")
            for f in page.frames:
                print(f"  {f.url or '(no url)'}")
            print("\nMake sure you are on the R&R Senior/Key Person Expanded webform,")
            print("not the Workspace overview. Click into the form so the webform iframe loads.")
            sys.exit(1)

        print(f"  Form iframe: {frame.url[:80]}")

        if not dry_run:
            page.screenshot(path=str(SS_DIR / "000_before_all.png"))

        # ── Phase 1: add and fill every person, no save yet ───────────────────
        person_logs = []
        all_filled: dict[int, dict] = {}  # n → filled fields map for verification

        for entry_i, entry in enumerate(entries):
            p = entry["person"]
            name = f"{p['first_name']}_{p['last_name']}".replace(" ", "_")
            print(f"\n[{entry_i+1}/{len(entries)}] Adding {p['first_name']} {p['last_name']} …")

            n_existing = _count_existing_persons(frame)
            n = n_existing + 1

            if not dry_run:
                frame.wait_for_selector(ADD_BUTTON_SEL, timeout=10000)
                frame.click(ADD_BUTTON_SEL)
                frame.wait_for_selector(f"#personFirstName{n}", timeout=15000)
                print(f"  block {n} appeared")
            else:
                print(f"  DRY-RUN: would click '{ADD_BUTTON_SEL}', wait for personFirstName{n}")

            field_result = _fill_person(frame, n, p, profile, dry_run)
            print(f"  filled {len(field_result['filled'])} fields, "
                  f"skipped {len(field_result['skipped'])}")
            if field_result["skipped"]:
                for fid, reason in field_result["skipped"].items():
                    print(f"    skip {fid}: {reason}")

            bio_path = entry["attachments"]["biosketch"].get("path")
            bio_status = _attach_file(frame, f"#personBioSketchsFile{n}", bio_path, dry_run)
            print(f"  biosketch: {bio_status or 'skipped (no path)'}")

            sup_entry = entry["attachments"]["current_pending_support"]
            sup_status = None
            if sup_entry.get("path"):
                sup_status = _attach_file(
                    frame, f"#personSupportsFile{n}", sup_entry["path"], dry_run
                )
                print(f"  support: {sup_status}")

            all_filled[n] = field_result["filled"]
            person_logs.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "add_person",
                "dry_run": dry_run,
                "person_index": n,
                "source_pdf": entry["source_pdf"],
                "source_element": entry["source_element"],
                "name": f"{p['first_name']} {p['last_name']}",
                "email": p["email"],
                "fields_filled": len(field_result["filled"]),
                "fields_skipped": field_result["skipped"],
                "biosketch_status": bio_status,
                "support_status": sup_status,
            })

            # Brief pause between persons so Knockout.js can settle
            if entry_i < len(entries) - 1:
                time.sleep(PAUSE_BETWEEN_PERSONS)

        # ── Phase 2: single save after all persons are entered ─────────────────
        print(f"\nSaving form ({len(entries)} person(s) added) …")
        save_status = _save_form(frame, page, dry_run)
        print(f"  save: {save_status}")

        ok_status = _click_ok_confirmation(frame, page, dry_run)
        if ok_status:
            print(f"  confirmation: {ok_status}")
            # Re-wait for network after OK click
            if not dry_run:
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

        if not dry_run:
            page.screenshot(path=str(SS_DIR / "999_after_save.png"))

        # ── Phase 3: verify all filled fields ─────────────────────────────────
        all_diffs: dict[int, list] = {}
        if not dry_run:
            for n, filled in all_filled.items():
                diffs = _verify_fields(frame, n, filled)
                if diffs:
                    all_diffs[n] = diffs
                    print(f"  VERIFICATION person {n} — {len(diffs)} diff(s):")
                    for d in diffs:
                        print(f"    {d}")

        # ── Write audit log ────────────────────────────────────────────────────
        with LOG_FILE.open("a") as lf:
            for log_entry in person_logs:
                log_entry["save_status"] = save_status
                log_entry["ok_confirmation"] = ok_status
                log_entry["verification_diffs"] = all_diffs.get(log_entry["person_index"], [])
                lf.write(json.dumps(log_entry) + "\n")

    print(f"\n{'DRY-RUN ' if dry_run else ''}Complete. Audit log: {LOG_FILE.relative_to(BASE)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(args.manifest, args.dry_run)
