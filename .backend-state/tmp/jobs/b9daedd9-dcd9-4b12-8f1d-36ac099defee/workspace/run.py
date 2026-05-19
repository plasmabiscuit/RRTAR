"""
CLI entry point for the RR import pipeline.

Key Person commands:
  fetch-schemas              Download and pin dependency XSDs from apply07.grants.gov
  extract   [input_dir]     Extract XFA XML + attachments from PDFs in input-pdfs/
  validate  [slots]         Schema + business-rule validation; generate validation_report.html
  normalize [--agency X]    Build import_manifest.json + import_manifest.xlsx
  automate  [--manifest P] [--dry-run]  Drive Grants.gov Key Person webform via Playwright

Budget commands:
  extract-budget  [input_dir]        Extract budget XML from PDFs in input-budget-pdfs/
  normalize-budget                   Build budget_manifest.json + budget_manifest.xlsx
  automate-budget [--manifest P] [--dry-run] [--save]  Drive Grants.gov Budget webform via Playwright

Performance Site commands:
  extract-performance-site [input_dir]        Extract Performance Site XML from PDFs in input-performance-site-pdfs/
  normalize-performance-site                  Build performance_site_manifest.json + .xlsx
  automate-performance-site [--manifest P] [--dry-run]  Drive Grants.gov Performance Site webform via Playwright

Shared:
  ui        [--port N]    Open dashboard at http://localhost:8080

Typical Key Person workflow:
  python3 run.py ui
  python3 run.py fetch-schemas
  # Drop Key Person PDFs into input-pdfs/
  python3 run.py extract
  python3 run.py normalize --agency NIH_PHS
  python3 run.py automate --dry-run
  python3 run.py automate

Typical Budget workflow:
  # Drop Budget PDFs into input-budget-pdfs/
  # Streamlyne summary PDFs can include an optional same-stem .budget.json
  # for fields such as uei, organization_name, budget_type,
  # key_person_roles, and budget_justification.
  python3 run.py extract-budget
  python3 run.py normalize-budget
  python3 run.py automate-budget --dry-run
  python3 run.py automate-budget
  python3 run.py automate-budget --save

Typical Performance Site workflow:
  # Drop Performance Site PDFs into input-performance-site-pdfs/
  python3 run.py extract-performance-site
  python3 run.py normalize-performance-site
  python3 run.py automate-performance-site --dry-run
  python3 run.py automate-performance-site
"""

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "scripts"))

_VENV_PYTHON = BASE / ".venv" / "bin" / "python3"


def _reexec_under_venv() -> None:
    """Replace the current process with the venv Python running the same command.

    Used when a dependency (playwright) is only available in .venv and the
    caller is using the system Python. os.execv is transparent — the terminal
    sees no difference.
    """
    if _VENV_PYTHON.exists() and sys.executable != str(_VENV_PYTHON):
        os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), __file__] + sys.argv[1:])


def cmd_fetch_schemas(args: list[str]) -> None:
    import fetch_schemas
    fetch_schemas.fetch(force="--force" in args)


def cmd_extract(args: list[str]) -> None:
    import extract
    input_dir = Path(args[0]) if args and not args[0].startswith("-") else None
    extract.run(input_dir)


def cmd_validate(args: list[str]) -> None:
    import validate
    slots = None
    for a in args:
        if a.isdigit():
            slots = int(a)
    validate.run(slots)


def cmd_normalize(args: list[str]) -> None:
    import normalize
    agency = "default"
    if "--agency" in args:
        idx = args.index("--agency")
        if idx + 1 < len(args):
            agency = args[idx + 1]
    normalize.run(agency)


def cmd_automate(args: list[str]) -> None:
    try:
        import playwright  # noqa: F401
    except ImportError:
        _reexec_under_venv()
        print("Error: playwright is not installed in the current Python environment.")
        print(f"Fix: {_VENV_PYTHON} -m pip install playwright  (venv already exists at .venv/)")
        sys.exit(1)
    import automate
    dry_run = "--dry-run" in args
    manifest = None
    if "--manifest" in args:
        idx = args.index("--manifest")
        if idx + 1 < len(args):
            manifest = Path(args[idx + 1])
    automate.run(manifest, dry_run)


def cmd_check_chrome(args: list[str]) -> None:
    _reexec_under_venv()
    import automate
    diag = automate.check_chrome()
    if not diag["port_open"]:
        debug_profile = BASE / ".chrome-debug-profile"
        print("✗  Port 9222 not open — Chrome is not running with --remote-debugging-port=9222")
        print()
        print("Chrome's security policy requires a non-default --user-data-dir.")
        print("Run:")
        print(f"  google-chrome --remote-debugging-port=9222 \\")
        print(f"    --user-data-dir={debug_profile}")
        print()
        print("Or click 'Launch Chrome (debug)' in the dashboard:  python3 run.py ui")
        return
    ver = diag.get("version", {}).get("Browser", "unknown")
    tabs = diag.get("tabs", [])
    print(f"✓  Chrome {ver}")
    print(f"   {len(tabs)} tab(s) open:")
    for t in tabs:
        print(f"   • {t.get('title','(no title)')[:60]}  {t.get('url','')[:60]}")


def cmd_extract_budget(args: list[str]) -> None:
    import extract_budget
    input_dir = Path(args[0]) if args and not args[0].startswith("-") else None
    extract_budget.run(input_dir)


def cmd_normalize_budget(args: list[str]) -> None:
    import normalize_budget
    normalize_budget.run()


def cmd_automate_budget(args: list[str]) -> None:
    try:
        import playwright  # noqa: F401
    except ImportError:
        _reexec_under_venv()
        print("Error: playwright is not installed.")
        sys.exit(1)
    import automate_budget
    dry_run = "--dry-run" in args
    save = "--save" in args
    manifest = None
    if "--manifest" in args:
        idx = args.index("--manifest")
        if idx + 1 < len(args):
            manifest = Path(args[idx + 1])
    automate_budget.run(manifest, dry_run, save)


def cmd_ui(args: list[str]) -> None:
    import ui
    port = 8080
    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            try:
                port = int(args[idx + 1])
            except ValueError:
                print(f"Invalid port '{args[idx + 1]}' — must be an integer. Using 8080.")

    ui.run(port)


def cmd_extract_performance_site(args: list[str]) -> None:
    import extract_performance_site
    input_dir = Path(args[0]) if args and not args[0].startswith("-") else None
    extract_performance_site.run(input_dir)


def cmd_normalize_performance_site(args: list[str]) -> None:
    import normalize_performance_site
    normalize_performance_site.run()


def cmd_automate_performance_site(args: list[str]) -> None:
    try:
        import playwright  # noqa: F401
    except ImportError:
        _reexec_under_venv()
        print("Error: playwright is not installed.")
        sys.exit(1)
    import automate_performance_site
    dry_run = "--dry-run" in args
    manifest = None
    if "--manifest" in args:
        idx = args.index("--manifest")
        if idx + 1 < len(args):
            manifest = Path(args[idx + 1])
    automate_performance_site.run(manifest, dry_run)


COMMANDS = {
    "fetch-schemas":    cmd_fetch_schemas,
    "extract":          cmd_extract,
    "validate":         cmd_validate,
    "normalize":        cmd_normalize,
    "automate":         cmd_automate,
    "extract-budget":   cmd_extract_budget,
    "normalize-budget": cmd_normalize_budget,
    "automate-budget":  cmd_automate_budget,
    "extract-performance-site": cmd_extract_performance_site,
    "normalize-performance-site": cmd_normalize_performance_site,
    "automate-performance-site": cmd_automate_performance_site,
    "check-chrome":     cmd_check_chrome,
    "ui":               cmd_ui,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        COMMANDS["ui"]([])
    elif sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("Available commands:", ", ".join(COMMANDS))
        sys.exit(1)
    else:
        COMMANDS[sys.argv[1]](sys.argv[2:])
