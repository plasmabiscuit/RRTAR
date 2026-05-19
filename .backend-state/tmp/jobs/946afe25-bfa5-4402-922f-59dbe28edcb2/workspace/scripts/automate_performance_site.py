"""
Playwright automation for the Project/Performance Site Location(s) webform.

Usage:
  python automate_performance_site.py [--manifest review/performance_site_manifest.json] [--dry-run]
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDIT_DIR = BASE / "audit"
SS_DIR = AUDIT_DIR / "performance_site_screenshots"
LOG_FILE = AUDIT_DIR / "run_log.jsonl"
SELECTOR_FILE = BASE / "config" / "selector_profile.grantsgov-performance-site-4.0.json"

CDP_URL = "http://127.0.0.1:9222"
IFRAME_SRC_PATTERN = "PerformanceSite_4_0"


def _load_manifest(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def _load_selector_profile() -> dict:
    return json.loads(SELECTOR_FILE.read_text())


def _fill_field(frame, selector: str, value: str, dry_run: bool) -> str | None:
    if value == "":
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


def _set_checkbox(frame, selector: str, checked: bool, dry_run: bool) -> str | None:
    if dry_run:
        return None
    try:
        el = frame.wait_for_selector(selector, timeout=5000)
        current = el.is_checked()
        if current != checked:
            el.click()
        return None
    except Exception as exc:
        return str(exc)


def _fill_site(frame, site: dict, ids: dict[str, str], dry_run: bool) -> dict:
    filled = {}
    skipped = {}

    checkbox_err = _set_checkbox(frame, ids["individual"], bool(site.get("individual")), dry_run)
    if checkbox_err:
        skipped[ids["individual"]] = checkbox_err
    else:
        filled[ids["individual"]] = bool(site.get("individual"))

    field_values = {
        ids["organization_name"]: site.get("organization_name", ""),
        ids["uei"]: site.get("uei", ""),
        ids["street1"]: site.get("street1", ""),
        ids["street2"]: site.get("street2", ""),
        ids["city"]: site.get("city", ""),
        ids["county"]: site.get("county", ""),
        ids["state"]: site.get("state", ""),
        ids["province"]: site.get("province", ""),
        ids["country"]: site.get("country", ""),
        ids["zip_postal_code"]: site.get("zip_postal_code", ""),
        ids["congressional_district"]: site.get("congressional_district", ""),
    }
    for field_id, value in field_values.items():
        if not value:
            continue
        err = _fill_field(frame, f"#{field_id}", value, dry_run)
        if err:
            skipped[field_id] = err
        else:
            filled[field_id] = value

    return {"filled": filled, "skipped": skipped}


def _add_other_site(frame, dry_run: bool) -> str | None:
    if dry_run:
        return None
    try:
        frame.locator("#addSite button").click()
        return None
    except Exception as exc:
        return str(exc)


def _entry_sites_as_additional(entry: dict) -> list[dict]:
    sites: list[dict] = []
    primary = entry.get("primary_site", {})
    if primary:
        sites.append(primary)
    sites.extend(entry.get("other_sites", []))
    return sites


def _attach_additional_sites(frame, path_str: str | None, dry_run: bool) -> str | None:
    if not path_str:
        return None
    p = BASE / path_str
    if not p.exists():
        return f"File not found: {p}"
    if dry_run:
        return f"DRY-RUN: would upload {p.name}"
    try:
        frame.locator("#additionalSiteFile").set_input_files(str(p))
        return f"uploaded {p.name}"
    except Exception as exc:
        return f"ERROR: {exc}"


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


def run(manifest_path: Path | None = None, dry_run: bool = False) -> None:
    manifest_path = manifest_path or (BASE / "review" / "performance_site_manifest.json")
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}. Run normalize-performance-site first.")
        sys.exit(1)

    entries = _load_manifest(manifest_path)
    if not entries:
        print("Performance site manifest is empty.")
        return

    profile = _load_selector_profile()
    SS_DIR.mkdir(parents=True, exist_ok=True)

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
            sys.exit(1)

        frame = None
        for _ in range(15):
            for f in page.frames:
                if IFRAME_SRC_PATTERN in f.url:
                    frame = f
                    break
            if frame:
                break
            time.sleep(1)
        if frame is None:
            print(f"Could not find iframe matching '{IFRAME_SRC_PATTERN}'.")
            sys.exit(1)

        if not dry_run:
            page.screenshot(path=str(SS_DIR / "000_before_all.png"))

        all_logs = []
        ids = profile["id_patterns"]
        next_other_idx = 1
        for entry in entries:
            print(f"\n{entry.get('source_pdf', '(unknown source)')}")
            additional_sites = _entry_sites_as_additional(entry)
            print(f"  Additional Sites to append: {len(additional_sites)}")

            entry_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "fill_performance_site",
                "dry_run": dry_run,
                "source_pdf": entry.get("source_pdf", ""),
                "mode": "append_all_as_additional",
                "additional_sites": [],
            }

            for site in additional_sites:
                row_idx = next_other_idx
                add_err = _add_other_site(frame, dry_run)
                if add_err:
                    entry_log["additional_sites"].append({"index": row_idx, "status": add_err})
                    print(f"  Additional Site {row_idx}: add failed: {add_err}")
                    continue
                if not dry_run:
                    frame.wait_for_selector(f"#otherOrganization{row_idx}, #otherCity{row_idx}", timeout=5000)
                    time.sleep(0.2)
                other_ids = {key: value.replace("{N}", str(row_idx)) for key, value in ids["other"].items()}
                other_result = _fill_site(frame, site, other_ids, dry_run)
                entry_log["additional_sites"].append({"index": row_idx, **other_result})
                print(
                    f"  Additional Site {row_idx}: "
                    f"filled={len(other_result['filled'])} skipped={len(other_result['skipped'])}"
                )
                next_other_idx += 1

            attach = entry.get("additional_sites_attachment", {})
            attach_status = _attach_additional_sites(frame, attach.get("path"), dry_run)
            if attach_status:
                print(f"  Additional Sites Attachment: {attach_status}")
                entry_log["additional_sites_attachment"] = attach_status

            all_logs.append(entry_log)

        print("\nSaving form …")
        save_status = _save_form(frame, page, dry_run)
        print(f"  save: {save_status}")

        if not dry_run:
            page.screenshot(path=str(SS_DIR / "999_after_save.png"))

        with LOG_FILE.open("a") as lf:
            for log_entry in all_logs:
                log_entry["save_status"] = save_status
                lf.write(json.dumps(log_entry) + "\n")

    print(f"\n{'DRY-RUN ' if dry_run else ''}Complete. Audit log: {LOG_FILE.relative_to(BASE)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(args.manifest, args.dry_run)
