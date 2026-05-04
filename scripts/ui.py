"""
Local dashboard for the RR import pipeline (Key Person + Budget).

Usage:
  python run.py          (default — opens dashboard)
  python run.py ui [--port 8080]
"""

import email
import base64
import html
import json
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE = Path(__file__).resolve().parents[1]
RUN_PY = BASE / "run.py"
INPUT_DIR        = BASE / "input-pdfs"
XML_DIR          = BASE / "extracted-xml"
ATT_DIR          = BASE / "extracted-attachments"
BUDGET_INPUT_DIR = BASE / "input-budget-pdfs"
BUDGET_XML_DIR   = BASE / "extracted-budget-xml"
BUDGET_ATT_DIR   = BASE / "extracted-budget-attachments"
PS_INPUT_DIR = BASE / "input-performance-site-pdfs"
PS_XML_DIR   = BASE / "extracted-performance-site-xml"
PS_ATT_DIR   = BASE / "extracted-performance-site-attachments"
REVIEW_DIR = BASE / "review"
AUDIT_DIR  = BASE / "audit"
DATA_DIR   = BASE / "data"


# ── data helpers ──────────────────────────────────────────────────────────────

def _read_log() -> list[dict]:
    log = AUDIT_DIR / "run_log.jsonl"
    if not log.exists():
        return []
    records = []
    for line in log.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _latest_extract_per_pdf(records: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for r in records:
        if r.get("status") != "ok":
            continue
        key = Path(r.get("source_pdf", "")).name
        latest[key] = r
    return latest


def _read_manifest() -> list[dict]:
    p = REVIEW_DIR / "import_manifest.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _clean_ws(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _read_contacts_directory() -> dict[str, dict]:
    path = DATA_DIR / "contacts.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}

    contacts: dict[str, dict] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        email_val = _clean_ws(str(value.get("email") or key)).lower()
        if not email_val:
            continue
        contacts[email_val] = value
    return contacts


def _contact_directory_payload() -> list[dict]:
    payload = []
    for email_val, contact in _read_contacts_directory().items():
        first = _clean_ws(str(contact.get("firstName") or ""))
        last = _clean_ws(str(contact.get("lastName") or ""))
        full_name = _clean_ws(str(contact.get("fullName") or f"{first} {last}"))
        payload.append({
            "email": email_val,
            "fullName": full_name or email_val,
            "title": _clean_ws(str(contact.get("jobTitle") or "")),
            "department": _clean_ws(str(contact.get("department") or "")),
        })
    payload.sort(key=lambda item: (item["fullName"].lower(), item["email"]))
    return payload


def _contact_campus_box_line(contact: dict) -> str:
    box = _clean_ws(str(contact.get("campusBox") or contact.get("Campus Box") or ""))
    return f"Campus Box {box}" if box else ""


def _manifest_entry_from_contact(contact: dict) -> dict:
    email_val = _clean_ws(str(contact.get("email") or ""))
    first = _clean_ws(str(contact.get("firstName") or ""))
    last = _clean_ws(str(contact.get("lastName") or ""))
    street2 = _contact_campus_box_line(contact)
    return {
        "source_pdf": "contacts.json",
        "source_element": "ContactDirectory",
        "source_index": 0,
        "target_action": "add_as_key_person",
        "exclude": False,
        "person": {
            "prefix": "",
            "first_name": first,
            "middle_name": "",
            "last_name": last,
            "suffix": "",
            "title": _clean_ws(str(contact.get("jobTitle") or "")),
            "organization_name": "Tennessee Technological University",
            "department": _clean_ws(str(contact.get("department") or "")),
            "division": _clean_ws(str(contact.get("Parent") or contact.get("unit") or "")),
            "credential": "",
            "project_role": "",
            "other_project_role_category": "",
            "degree_type": "",
            "degree_year": "",
            "address": {
                "street1": "1 William L. Jones Dr",
                "street2": street2,
                "city": "",
                "county": "",
                "state": "",
                "province": "",
                "country": "",
                "postal_code": "",
            },
            "phone": _clean_ws(str(contact.get("workPhone") or "")),
            "fax": "",
            "email": email_val,
        },
        "attachments": {
            "biosketch": {
                "required": True,
                "source": "contacts-directory",
                "path": "",
                "sha1_base64": None,
            },
            "current_pending_support": {
                "required": False,
                "source": "contacts-directory",
                "path": "",
                "sha1_base64": None,
            },
        },
        "validation": {
            "schema_valid": True,
            "business_rules_valid": False,
            "warnings": [
                "Added from contacts.json; review role, email, and attachments before automate."
            ],
        },
    }


def _input_pdfs() -> list[Path]:
    INPUT_DIR.mkdir(exist_ok=True)
    return sorted(INPUT_DIR.glob("*.pdf"))


# ── budget data helpers ───────────────────────────────────────────────────────

def _read_budget_log() -> list[dict]:
    return [r for r in _read_log() if r.get("form_type") == "budget"]


def _latest_budget_extract_per_pdf(records: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for r in records:
        if r.get("status") != "ok":
            continue
        key = Path(r.get("source_pdf", "")).name
        latest[key] = r
    return latest


def _read_budget_manifest() -> list[dict]:
    p = REVIEW_DIR / "budget_manifest.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _budget_input_pdfs() -> list[Path]:
    BUDGET_INPUT_DIR.mkdir(exist_ok=True)
    return sorted(BUDGET_INPUT_DIR.glob("*.pdf"))


def _read_performance_site_log() -> list[dict]:
    return [r for r in _read_log() if r.get("form_type") == "performance_site"]


def _latest_performance_site_extract_per_pdf(records: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for r in records:
        if r.get("status") != "ok":
            continue
        key = Path(r.get("source_pdf", "")).name
        latest[key] = r
    return latest


def _read_performance_site_manifest() -> list[dict]:
    p = REVIEW_DIR / "performance_site_manifest.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _performance_site_input_pdfs() -> list[Path]:
    PS_INPUT_DIR.mkdir(exist_ok=True)
    return sorted(PS_INPUT_DIR.glob("*.pdf"))


def _performance_site_pipeline_steps(ps_pdfs, ps_extract_map, ps_manifest) -> list[dict]:
    return [
        {
            "name": "extract-performance-site",
            "done": bool(ps_extract_map),
            "cmd":  "extract-performance-site",
            "args": [],
            "hint": "Parse XFA XML + attachments from Performance Site PDFs",
            "enabled": bool(ps_pdfs),
        },
        {
            "name": "normalize-performance-site",
            "done": bool(ps_manifest),
            "cmd":  "normalize-performance-site",
            "args": [],
            "hint": "Build performance_site_manifest.json + .xlsx for review",
            "enabled": bool(ps_extract_map),
        },
    ]


def _budget_pipeline_steps(budget_pdfs, budget_extract_map, budget_manifest) -> list[dict]:
    return [
        {
            "name": "extract-budget",
            "done": bool(budget_extract_map),
            "cmd":  "extract-budget",
            "args": [],
            "hint": "Parse XFA or Streamlyne budget PDFs into XML + attachments",
            "enabled": bool(budget_pdfs),
        },
        {
            "name": "normalize-budget",
            "done": bool(budget_manifest),
            "cmd":  "normalize-budget",
            "args": [],
            "hint": "Build budget_manifest.json + .xlsx for review",
            "enabled": bool(budget_extract_map),
        },
    ]


def _pipeline_steps(input_pdfs, extract_map, manifest) -> list[dict]:
    return [
        {
            "name": "fetch-schemas",
            "done": (BASE / "schemas" / "Attachments-V1.0.xsd").exists(),
            "cmd": "fetch-schemas",
            "args": [],
            "hint": "Download and pin Grants.gov XSD schemas",
        },
        {
            "name": "extract",
            "done": bool(extract_map),
            "cmd": "extract",
            "args": [],
            "hint": "Parse XFA XML + attachments from input PDFs",
            "enabled": bool(input_pdfs),
        },
        {
            "name": "validate",
            "done": (REVIEW_DIR / "validation_report.html").exists(),
            "cmd": "validate",
            "args": [],
            "hint": "Schema + business-rule validation",
            "enabled": bool(extract_map),
        },
        {
            "name": "normalize",
            "done": bool(manifest),
            "cmd": "normalize",
            "args": [],
            "hint": "Build import_manifest.json + .xlsx for review",
            "enabled": bool(extract_map),
        },
    ]


def _chrome_debug_status() -> dict:
    import socket, urllib.request
    try:
        with socket.create_connection(("127.0.0.1", 9222), timeout=0.5):
            pass
    except OSError:
        return {"open": False, "tabs": 0, "version": ""}
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2) as r:
            v = json.loads(r.read())
        with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=2) as r:
            tabs = json.loads(r.read())
        return {"open": True, "tabs": len(tabs), "version": v.get("Browser", "")}
    except Exception:
        return {"open": True, "tabs": 0, "version": ""}


def _find_chrome() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _spawn_step(step: str, extra_args: list[str]) -> None:
    subprocess.Popen(
        [sys.executable, str(RUN_PY), step] + extra_args,
        cwd=str(BASE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _parse_multipart_pdfs(content_type: str, body: bytes) -> list[tuple[str, bytes]]:
    """Parse multipart/form-data body; return (filename, data) for .pdf parts."""
    msg = email.message_from_bytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + body
    )
    results = []
    for part in msg.walk():
        fname = part.get_filename()
        if fname and fname.lower().endswith(".pdf"):
            data = part.get_payload(decode=True)
            if data:
                results.append((Path(fname).name, data))
    return results


# ── agency / settings ────────────────────────────────────────────────────────

_AGENCIES = [
    ("NIH_PHS", "NIH / PHS"),
    ("NSF",     "NSF"),
    ("DOD",     "DoD"),
    ("default", "Default"),
]

_RR_PROJECT_ROLES = [
    "",
    "PD/PI",
    "Co-PD/PI",
    "Co-Investigator",
    "Faculty Collaborator",
    "Graduate Student (Research Assistant)",
    "Postdoctoral Associate",
    "Research Scientist",
    "Technician",
    "Undergraduate Student",
    "Other Professional",
    "Other (specify)",
]

_UI_SETTINGS = BASE / "config" / "ui_settings.json"


def _read_ui_settings() -> dict:
    if _UI_SETTINGS.exists():
        try:
            return json.loads(_UI_SETTINGS.read_text())
        except Exception:
            pass
    return {"agency": "default"}


def _write_ui_settings(settings: dict) -> None:
    _UI_SETTINGS.parent.mkdir(exist_ok=True)
    _UI_SETTINGS.write_text(json.dumps(settings, indent=2))


_ICON_ASSETS = {
    "addressbook": {
        "sm": "icons/PNG/for-dark-mode/16px/regular/book-bookmark.png",
        "lg": "icons/PNG/for-dark-mode/48px/regular/book-bookmark.png",
    },
    "automate": {
        "sm": "icons/PNG/for-light-mode/16px/solid/file-import.png",
        "lg": "icons/PNG/for-light-mode/48px/solid/file-import.png",
    },
    "budget": {
        "sm": "icons/PNG/for-light-mode/16px/solid/receipt.png",
        "lg": "icons/PNG/for-light-mode/48px/solid/receipt.png",
    },
    "check": {
        "sm": "icons/PNG/for-light-mode/16px/regular/check.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/check.png",
    },
    "close": {
        "sm": "icons/PNG/for-light-mode/16px/regular/times.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/times.png",
    },
    "cloud-upload": {
        "sm": "icons/PNG/for-light-mode/16px/regular/cloud-upload.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/cloud-upload.png",
    },
    "pipeline": {
        "sm": "img/pipe.png",
        "lg": "img/pipe.png",
    },
    "file": {
        "sm": "icons/PNG/for-light-mode/16px/regular/notebook.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/notebook.png",
    },
    "folder": {
        "sm": "icons/PNG/for-dark-mode/16px/solid/folder-open.png",
        "lg": "icons/PNG/for-dark-mode/48px/solid/folder-open.png",
    },
    "globe": {
        "sm": "icons/PNG/for-light-mode/16px/regular/globe.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/globe.png",
    },
    "manifest": {
        "sm": "icons/PNG/for-dark-mode/16px/solid/clipboard.png",
        "lg": "icons/PNG/for-dark-mode/48px/solid/clipboard.png",
    },
    "pause": {
        "sm": "icons/PNG/for-light-mode/16px/regular/pause.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/pause.png",
    },
    "people": {
        "sm": "icons/PNG/for-light-mode/16px/solid/user.png",
        "lg": "icons/PNG/for-light-mode/48px/solid/user.png",
    },
    "pdfschip": {
        "sm": "img/pdfs.png",
        "lg": "img/pdfs.png",
    },
    "pin": {
        "sm": "icons/PNG/for-light-mode/16px/regular/location-pin.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/location-pin.png",
    },
    "play": {
        "sm": "icons/PNG/for-light-mode/16px/regular/play.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/play.png",
    },
    "manifestchip": {
        "sm": "img/manifest.png",
        "lg": "img/manifest.png",
    },
    "pipelinechip": {
        "sm": "img/pipeline.png",
        "lg": "img/pipeline.png",
    },
    "save": {
        "sm": "icons/PNG/for-light-mode/16px/regular/save.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/save.png",
    },
    "trash": {
        "sm": "icons/PNG/for-light-mode/16px/regular/trash.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/trash.png",
    },
    "upload": {
        "sm": "icons/PNG/for-light-mode/16px/regular/upload-alt.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/upload-alt.png",
    },
    "warning": {
        "sm": "icons/PNG/for-light-mode/16px/regular/exclaimation.png",
        "lg": "icons/PNG/for-light-mode/48px/regular/exclaimation.png",
    },
}


_ICON_DATA_CACHE: dict[tuple[str, str], str] = {}
_FONT_DATA_CACHE: dict[str, str] = {}


def _icon_data_uri(name: str, size: str = "sm") -> str:
    key = (name, size)
    cached = _ICON_DATA_CACHE.get(key)
    if cached:
        return cached
    path = BASE / _ICON_ASSETS[name][size]
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    data_uri = f"data:image/png;base64,{encoded}"
    _ICON_DATA_CACHE[key] = data_uri
    return data_uri


def _font_data_uri(filename: str) -> str:
    cached = _FONT_DATA_CACHE.get(filename)
    if cached:
        return cached
    path = BASE / "fonts" / filename
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    data_uri = f"data:font/ttf;base64,{encoded}"
    _FONT_DATA_CACHE[filename] = data_uri
    return data_uri


def _icon(name: str, label: str = "", classes: str = "") -> str:
    label_attr = f' aria-label="{html.escape(label)}"' if label else ""
    class_attr = f"icon {classes}".strip()
    size = "lg" if "icon-chip" in classes else "sm"
    return (
        f'<span class="{class_attr}"{label_attr}>'
        f'<img src="{_icon_data_uri(name, size)}" alt="" aria-hidden="true">'
        f"</span>"
    )


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
@font-face {
  font-family: "RasterForge";
  src: url("__RASTERFORGE_FONT__") format("truetype");
  font-display: block;
}
@font-face {
  font-family: "PixeloidSans";
  src: url("__PIXELOID_FONT__") format("truetype");
  font-display: block;
}
@font-face {
  font-family: "NineteenNinety";
  src: url("__NINETEEN_FONT__") format("truetype");
  font-display: block;
}
@font-face {
  font-family: "DosReadable";
  src: url("__DOSREADABLE_FONT__") format("truetype");
  font-display: block;
}
:root {
  --primary: #582c83;
  --primary-strong: #45236a;
  --primary-deep: #2a133f;
  --primary-soft: #ede4f6;
  --primary-mist: #f8f4fc;
  --accent: #FFD100;
  --accent-deep: #d6aa00;
  --success: #1a7f64;
  --success-soft: #e6f5ef;
  --warning: #9a6100;
  --warning-soft: #fff2c8;
  --danger: #b43753;
  --danger-soft: #fcebf0;
  --ink: #221d2c;
  --muted: #6a647a;
  --muted-soft: #978ea8;
  --line: #cfc0e1;
  --panel: rgba(255,255,255,.94);
  --shadow: 0 10px 0 rgba(88, 44, 131, 0.10), 0 22px 36px rgba(45, 18, 63, 0.10);
  --radius: 10px;
  --icon-primary-filter: brightness(0) saturate(100%) invert(20%) sepia(47%) saturate(1912%) hue-rotate(245deg) brightness(95%) contrast(92%);
  --pixel-button-border-purple: url("/img/button-border-purple.svg");
  --pixel-button-border-green: url("/img/button-border-green.svg");
  --pixel-button-border-red: url("/img/button-border-red.svg");
  --pixel-button-border-orange: url("/img/button-border-orange.svg");
  --pixel-button-border-slate: url("/img/button-border-slate.svg");
  --pixel-button-border: var(--pixel-button-border-purple);
  --purple: var(--primary);
  --purple-deep: var(--primary-deep);
  --purple-mid: var(--primary-strong);
  --purple-lt: var(--primary-soft);
  --purple-xlt: var(--primary-mist);
  --yellow: var(--accent);
  --yellow-dark: var(--accent-deep);
}
* { box-sizing: border-box; }
button, input, select, textarea { font: inherit; }
body {
  font-family: "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif;
  margin: 0;
  min-height: 100vh;
  position: relative;
  isolation: isolate;
  color: var(--ink);
  background:
    radial-gradient(circle at 50% -10%, rgba(203, 170, 255, .34), transparent 26rem),
    radial-gradient(circle at 20% 18%, rgba(115, 67, 170, .22), transparent 24rem),
    radial-gradient(circle at 82% 12%, rgba(84, 42, 135, .20), transparent 26rem),
    linear-gradient(180deg, #20132f 0%, #2a183d 22%, #22172f 58%, #160f1d 100%);
  background-attachment: fixed;
}
body::before,
body::after {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
}
body::before {
  z-index: -2;
  opacity: .88;
  background:
    radial-gradient(circle at 50% 45%, rgba(215, 176, 255, .16), transparent 0 36%),
    radial-gradient(circle at 50% 50%, rgba(112, 66, 171, .16), transparent 58%),
    repeating-linear-gradient(
      180deg,
      rgba(255,255,255,.032) 0 1px,
      rgba(26, 14, 39, 0) 1px 4px
    ),
    linear-gradient(
      90deg,
      rgba(255, 40, 120, .028) 0,
      rgba(120, 180, 255, .02) 48%,
      rgba(180, 80, 255, .032) 100%
    );
  mix-blend-mode: screen;
  animation: crt-flicker 9s steps(12) infinite;
}
body::after {
  z-index: -1;
  background:
    radial-gradient(circle at 50% 50%, transparent 58%, rgba(7, 4, 12, .28) 88%, rgba(0, 0, 0, .52) 100%),
    linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,0) 18%, rgba(0,0,0,.16) 100%);
  box-shadow:
    inset 0 0 120px rgba(196, 127, 255, .10),
    inset 0 0 260px rgba(0, 0, 0, .42);
}
@keyframes crt-flicker {
  0%, 100% { opacity: .84; }
  8% { opacity: .87; }
  14% { opacity: .81; }
  37% { opacity: .9; }
  53% { opacity: .83; }
  79% { opacity: .88; }
}
header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  padding: .95rem 2rem;
  color: #fff;
  backdrop-filter: blur(16px);
  background:
    linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px),
    linear-gradient(135deg, rgba(42,19,63,.9), rgba(88,44,131,.82));
  background-size: 18px 18px, 18px 18px, auto;
  border-bottom: 3px solid var(--accent);
  box-shadow: 0 10px 0 rgba(42,19,63,.18), 0 18px 30px rgba(45, 18, 63, 0.14);
}
header .header-brand {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-width: 0;
  flex: 1 1 auto;
}
header .header-brand-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: .2rem;
  min-width: 0;
}
header .header-badge {
  display: block;
  width: clamp(2.8rem, 5vw, 4.4rem);
  height: clamp(2.8rem, 5vw, 4.4rem);
  object-fit: contain;
  image-rendering: pixelated;
  filter: drop-shadow(0 2px 0 rgba(34, 15, 52, .35));
  flex: 0 0 auto;
}
header h1 { margin: 0; font-family: "RasterForge", monospace; font-size: 1.4rem; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
header h1 span.accent { color: var(--accent); }
header .sub {
  font-family: "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif;
  font-size: .82rem;
  opacity: .72;
  letter-spacing: .05em;
  text-transform: uppercase;
}
main { position: relative; z-index: 1; max-width: 1480px; margin: 1.5rem auto; padding: 0 1.25rem 1.5rem; }
.row2 { display: grid; grid-template-columns: 380px 1fr; gap: 1.1rem;
        margin-bottom: 1.1rem; }
.card {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(239,229,249,.98), rgba(220,204,239,.98) 46%, rgba(189,167,220,.99) 100%);
  border: 1px solid rgba(91, 59, 129, .48);
  border-radius: var(--radius);
  padding: 1.2rem 1.35rem;
  box-shadow:
    0 0 0 2px rgba(245,238,252,.42),
    inset 0 1px 0 rgba(255,255,255,.88),
    inset 0 -18px 28px rgba(69, 37, 105, .16),
    inset 0 18px 26px rgba(255,255,255,.10),
    inset 0 0 0 1px rgba(255,255,255,.35),
    var(--shadow);
}
.card::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(135deg, rgba(255,255,255,.34), transparent 22%, rgba(123, 81, 177, .08) 56%, rgba(88,44,131,.14) 100%),
    repeating-linear-gradient(90deg, rgba(255,255,255,.05) 0 2px, rgba(147, 115, 193, .06) 2px 14px);
  opacity: .9;
}
.card::after {
  content: "";
  position: absolute;
  inset: 10px;
  border-radius: 7px;
  border: 1px solid rgba(111, 79, 156, .18);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.28);
  pointer-events: none;
}
.card h2 {
  position: relative;
  margin: 0 0 1rem;
  font-family: "NineteenNinety", "PixeloidSans", sans-serif;
  font-size: .92rem;
  font-weight: 800;
  color: var(--primary-deep);
  border-bottom: 2px solid rgba(106, 80, 144, .22);
  padding: 0 0 .72rem;
  display: flex;
  align-items: center;
  gap: .6rem;
  text-transform: uppercase;
  letter-spacing: .06em;
  text-shadow: 0 1px 0 rgba(255,255,255,.72);
}
.card h2::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 3px;
  background: linear-gradient(90deg, var(--accent), rgba(255,209,0,.1) 55%, transparent);
}
.icon { display: inline-flex; align-items: center; justify-content: center; width: 1rem; height: 1rem; flex: 0 0 auto; }
.icon img { width: 100%; height: 100%; image-rendering: pixelated; image-rendering: crisp-edges; display: block; }
.icon-chip {
  width: 2.475rem;
  height: 2.475rem;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border-radius: 0;
  background: url("/img/Block.png") no-repeat center / contain;
  box-shadow: none;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  filter: drop-shadow(0 2px 0 rgba(42,19,63,.28));
}
.icon-chip img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  filter: none;
}
.icon-btn { width: .95rem; height: .95rem; }
.icon-status { width: .8rem; height: .8rem; }
.btn-primary .icon img,
.btn-success .icon img,
.btn-danger .icon img,
.btn-warn .icon img,
.btn-run .icon img,
.btn-automate .icon img,
.tab-btn.active .icon img,
.refresh-toggle-btn .icon img,
.refresh-toggle-btn.paused .icon img {
  filter: brightness(0) invert(1);
}
.steps { list-style: none; margin: 0; padding: 0; }
.steps li { display: grid; grid-template-columns: 5.4rem minmax(0, 1fr) auto;
            align-items: center; column-gap: .7rem; row-gap: .16rem;
            padding: .42rem 0; font-size: .88rem; }
.step-action { grid-column: 1; }
.step-name { grid-column: 2; font-weight: 800; color: var(--primary-deep);
             letter-spacing: .03em; text-transform: uppercase; }
.step-state { grid-column: 3; justify-self: end; }
.step-hint { grid-column: 2 / -1; font-size: .75rem; color: var(--muted); }
.step-badge { min-width: 1.7rem; justify-content: center; padding-left: .34rem; padding-right: .34rem; }
.step-badge.done { color: var(--success); background: var(--success-soft); border-color: rgba(18,122,99,.14); }
.step-btn { width: 100%; min-width: 0; }
.badge { display: inline-flex; align-items: center; gap: .28rem; border-radius: 6px; padding: .24rem .52rem; font-size: .69rem; font-weight: 900; white-space: nowrap; letter-spacing: .05em; border: 2px solid transparent; text-transform: uppercase; font-family: "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif; }
.ok   { background: var(--success-soft); color: var(--success); border-color: rgba(18,122,99,.14); }
.warn { background: var(--warning-soft); color: var(--warning); border-color: rgba(159,98,0,.14); }
.err  { background: var(--danger-soft); color: var(--danger); border-color: rgba(186,49,72,.14); }
.pend { background: #eef1f6; color: var(--muted); border-color: rgba(102,112,133,.14); }
.done { background: var(--primary-soft); color: var(--primary); border-color: rgba(88,44,131,.12); }
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: .83rem; }
th { background: linear-gradient(180deg, var(--primary), var(--primary-strong)); color: #fff; padding: .62rem .7rem; text-align: left; white-space: nowrap; font-weight: 800; letter-spacing: .03em; text-transform: uppercase; }
th:first-child { border-top-left-radius: 8px; }
th:last-child { border-top-right-radius: 8px; }
td { padding: .55rem .7rem; border-bottom: 1px solid rgba(88,44,131,.08); vertical-align: top; }
tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: rgba(88,44,131,.035); }
.mono { font-family: 'SF Mono', 'Fira Mono', monospace; font-size: .78rem; }
.chrome-box { margin-top: .9rem; display: flex; gap: .7rem; align-items: flex-start;
              flex-wrap: wrap; }
.chrome-info { font-size: .78rem; color: var(--muted); max-width: 320px; line-height: 1.5; }
button, .btn { --button-fill: linear-gradient(180deg, #efe8f8, #d8cde7); --pixel-outer-shape: polygon(4px 0, calc(100% - 4px) 0, calc(100% - 2px) 2px, 100% 4px, 100% calc(100% - 4px), calc(100% - 2px) calc(100% - 2px), calc(100% - 4px) 100%, 4px 100%, 2px calc(100% - 2px), 0 calc(100% - 4px), 0 4px, 2px 2px); cursor: pointer; position: relative; overflow: hidden; isolation: isolate; border: 4px solid transparent; border-image-source: var(--pixel-button-border); border-image-slice: 6; border-image-width: 4px; border-image-repeat: stretch; border-radius: 0; background: var(--button-fill); background-clip: padding-box; clip-path: var(--pixel-outer-shape); font-size: .8rem; font-weight: 800; display: inline-flex; align-items: center; justify-content: center; gap: .42rem; transition: transform .12s ease, box-shadow .18s ease, background .18s ease, color .18s ease; text-transform: uppercase; letter-spacing: .05em; font-family: "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif; box-shadow: inset 0 1px 0 rgba(255,255,255,.28), inset 0 -2px 0 rgba(0,0,0,.12); }
button::before, .btn::before { content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none; clip-path: var(--pixel-outer-shape); background: linear-gradient(180deg, rgba(255,255,255,.24), rgba(255,255,255,0) 42%, rgba(0,0,0,.12) 100%), repeating-linear-gradient(90deg, rgba(255,255,255,.08) 0 2px, transparent 2px 12px); opacity: .72; }
button::after, .btn::after { content: none; }
button:hover, .btn:hover { transform: translateY(-1px); }
button:active, .btn:active { transform: translateY(2px); }
button:disabled, .btn:disabled { transform: none; }
.btn-primary { --pixel-button-border: var(--pixel-button-border-purple); --button-fill: linear-gradient(180deg, #7a49ae, var(--primary) 54%, var(--primary-strong)); color: #fff; padding: .38rem .86rem; box-shadow: 0 4px 0 rgba(42,19,63,.34), 0 9px 16px rgba(42,19,63,.18); text-shadow: 0 1px 0 rgba(42,19,63,.42); }
.btn-primary:hover { --button-fill: linear-gradient(180deg, var(--primary-strong), var(--primary-deep)); }
.btn-success { --pixel-button-border: var(--pixel-button-border-green); --button-fill: linear-gradient(180deg, #229073, var(--success) 54%, #0f6250); color: #fff; padding: .38rem .86rem; box-shadow: 0 4px 0 rgba(15,98,80,.28), 0 9px 16px rgba(15,98,80,.16); text-shadow: 0 1px 0 rgba(8,63,52,.35); }
.btn-success:hover { --button-fill: linear-gradient(180deg, #0f6250, #0b5142); }
.btn-danger  { --pixel-button-border: var(--pixel-button-border-red); --button-fill: linear-gradient(180deg, #ca4c69, var(--danger) 54%, #97263a); color: #fff; padding: .22rem .6rem; font-size: .74rem; box-shadow: 0 3px 0 rgba(151,38,58,.3), 0 7px 12px rgba(151,38,58,.14); text-shadow: 0 1px 0 rgba(94,24,37,.35); }
.btn-danger:hover { --button-fill: linear-gradient(180deg, #a42a40, #861f31); }
.btn-warn    { --pixel-button-border: var(--pixel-button-border-orange); --button-fill: linear-gradient(180deg, #ea900d, #d07200 54%, #ab5300); color: #fff; padding: .22rem .7rem; font-size: .76rem; box-shadow: 0 3px 0 rgba(171,83,0,.28), 0 7px 12px rgba(171,83,0,.14); text-shadow: 0 1px 0 rgba(110,53,0,.34); }
.btn-warn:hover { --button-fill: linear-gradient(180deg, #b66200, #8f4300); }
.btn-sm      { padding: .13rem .43rem; font-size: .75rem; }
.btn-disabled { --pixel-button-border: var(--pixel-button-border-slate); --button-fill: linear-gradient(180deg, #ede9f2, #d7d0e0); color: #98a2b3; cursor: not-allowed; padding: .4rem .88rem; box-shadow: 0 1px 0 rgba(80,72,92,.18); }
.btn-disabled::before { opacity: .34; }
.btn-run { --pixel-button-border: var(--pixel-button-border-purple); --button-fill: linear-gradient(180deg, #8a59b9, #6d3aa0 48%, var(--primary)); color: #fff; padding: .16rem .58rem; font-size: .71rem; box-shadow: 0 3px 0 rgba(42,19,63,.32), 0 7px 12px rgba(42,19,63,.15); text-shadow: 0 1px 0 rgba(42,19,63,.38); }
.btn-run:hover { --button-fill: linear-gradient(180deg, var(--primary), var(--primary-deep)); color: #fff; }
.btn-automate { --pixel-button-border: var(--pixel-button-border-purple); --button-fill: linear-gradient(180deg, #8f63ba, #7340a7 40%, var(--primary)); color: #fff; padding: .5rem 1.18rem; font-size: .86rem; font-weight: 900; box-shadow: 0 4px 0 rgba(42,19,63,.34), 0 10px 18px rgba(88, 44, 131, 0.22); text-shadow: 0 1px 0 rgba(42,19,63,.42); }
.btn-automate:hover { --button-fill: linear-gradient(180deg, var(--primary), var(--primary-deep)); color: #fff; }
.btn-panel { width: 12rem; }
button:active::before, .btn:active::before { opacity: .5; }
.btn-primary:active, .btn-success:active, .btn-danger:active, .btn-warn:active, .btn-run:active, .btn-automate:active { box-shadow: 0 1px 0 rgba(42,19,63,.24); }

/* Drop zone */
.drop-zone { border: 2px dashed rgba(88, 44, 131, .28); border-radius: 10px; padding: 1.3rem;
             text-align: center; color: #8465a5; cursor: pointer;
             transition: border-color .18s, background .18s, transform .18s; margin-bottom: .9rem;
             background: linear-gradient(180deg, rgba(255,255,255,.88), rgba(239,232,247,.72)), radial-gradient(circle at top, rgba(88,44,131,.16), transparent 11rem);
             box-shadow: inset 0 0 0 1px rgba(255,255,255,.7); }
.drop-zone:hover, .drop-zone.drag-over { border-color: var(--primary);
             background: linear-gradient(180deg, rgba(255,255,255,.96), rgba(239,232,247,.88)); color: var(--primary); transform: translateY(-1px); }
.drop-zone input[type=file] { display: none; }
.drop-zone .dz-icon { width: 3rem; height: 3rem; margin: 0 auto .45rem; border-radius: 8px; color: var(--primary); background: linear-gradient(180deg, rgba(109,58,160,.28), rgba(88,44,131,.08)); box-shadow: inset 0 0 0 2px rgba(88,44,131,.08); padding: .55rem; }
.drop-zone .dz-icon .icon { width: 100%; height: 100%; }
.drop-zone .dz-icon .icon img { filter: var(--icon-primary-filter); }
.drop-zone p { margin: 0; font-size: .83rem; }

/* Manifest */
.manifest-wrap { overflow-x: auto; }
.att-ok   { color: var(--success); font-size: .8rem; }
.att-miss { color: var(--danger); font-style: italic; font-size: .8rem; }
.warn-list { margin: .2rem 0 0 1rem; padding: 0; list-style: disc; font-size: .77rem; color: var(--warning); }
.person-name { font-weight: 600; font-size: .88rem; }
.person-src  { font-size: .72rem; color: var(--muted); }
.sub-info    { font-size: .75rem; color: #4f5b6d; }
.sub-dim     { font-size: .73rem; color: var(--muted); }
.kp-manifest .person-src,
.kp-manifest .sub-dim {
  font-size: .79rem;
}
.cred-tag    { font-family: monospace; font-size: .75rem; color: var(--primary); font-weight: 700; }
.footer-note-wrap { position: relative; width: fit-content; max-width: 100%;
                    margin: 1.5rem auto 0; padding-top: clamp(4rem, 6vw, 5rem); }
.refresh-note { font-size: .75rem; color: var(--muted); margin: 0;
                text-align: center; line-height: 1.45; padding-bottom: 1.5rem; }
.automate-row { margin-top: .9rem; display: flex; gap: .7rem; align-items: center; }
.header-actions { margin-left: auto; display: flex; flex-direction: column; gap: .45rem; align-items: stretch; }
.header-utility-btn { width: 9.25rem; justify-content: center; }

/* Tab navigation */
.tab-bar { display: inline-flex; gap: .35rem; padding: .35rem; border: 2px solid rgba(88,44,131,.08); border-radius: 10px; background: #8f79a473; box-shadow: var(--shadow); font-family: "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif; }
header .tab-bar { margin-left: 0; }
.tab-btn { --pixel-button-border: var(--pixel-button-border-slate); --button-fill: linear-gradient(180deg, #f2edf6, #ddd5e6); padding: .58rem .95rem; font-size: .82rem; font-weight: 900; color: var(--muted); font-family: "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif; box-shadow: 0 2px 0 rgba(80,72,92,.16); }
.tab-btn:hover { --button-fill: linear-gradient(180deg, #efe8f8, #d9cdea); color: var(--primary); }
.tab-btn.active { --pixel-button-border: var(--pixel-button-border-purple); --button-fill: linear-gradient(180deg, #7c4bb0, var(--primary), var(--primary-strong)); color: #fff; box-shadow: 0 4px 0 rgba(42,19,63,.28); text-shadow: 0 1px 0 rgba(42,19,63,.38); }

/* Budget manifest */
.budget-org { font-weight: 700; font-size: .9rem; }
.budget-period-hdr { font-weight: 800; font-size: .84rem; color: var(--primary-deep);
                     margin: .7rem 0 .35rem; padding: .45rem .65rem;
                     background: linear-gradient(180deg, rgba(109,58,160,.12), rgba(88,44,131,.08)); border-radius: 8px; border: 2px solid rgba(88,44,131,.08); text-transform: uppercase; letter-spacing: .04em; }
.bgt-table-wrap { overflow-x: auto; margin-bottom: .4rem; }
.bgt-table { width: 100%; border-collapse: collapse; font-size: .79rem; }
.bgt-col-hdr th { background: var(--primary-strong); color: #fff; padding: .38rem .55rem;
                  text-align: left; white-space: nowrap; font-size: .73rem; font-weight: 700; }
.bgt-col-hdr th.bgt-amt,
.bgt-col-hdr th.bgt-num { text-align: right; }
.bgt-sec-hdr td { background: var(--primary-deep); color: #fff; font-weight: 700;
                  font-size: .76rem; letter-spacing: .04em; padding: .25rem .6rem; }
.bgt-data-row td { padding: .32rem .55rem; border-bottom: 1px solid rgba(88,44,131,.08); }
.bgt-data-row:hover td { background: rgba(88,44,131,.04); }
.bgt-label { text-align: left; min-width: 160px; }
.bgt-detail { text-align: left; color: var(--muted); font-size: .74rem; min-width: 90px; }
.bgt-num { text-align: right; white-space: nowrap; color: #4f5b6d; min-width: 50px; font-family: "DosReadable", "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif; font-size: .88rem; }
.bgt-amt { text-align: right; white-space: nowrap; min-width: 82px; font-family: "DosReadable", "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif; font-size: .88rem; }
.bgt-funds { font-weight: 600; color: var(--primary-deep); font-family: "DosReadable", "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif; font-size: .88rem; }
.bgt-total-row td { background: rgba(88,44,131,.08); border-top: 1px solid var(--line); }
.bgt-total-label { text-align: right; padding-right: .65rem; font-weight: 700;
                   font-size: .76rem; color: var(--primary); }
.bgt-subtotal-row td { background: var(--primary-strong); color: #fff !important;
                       border-top: 2px solid var(--primary-deep); }
.bgt-subtotal-row .bgt-total-label,
.bgt-subtotal-row .bgt-funds { color: #fff !important; }
.bgt-grand-total-row td { background: var(--primary-deep); color: #fff !important;
                          font-weight: 700; }
.bgt-grand-total-row .bgt-total-label { color: #fff !important; }
.bgt-grand-total-row .bgt-funds { color: var(--accent) !important; }
a { color: var(--primary); }
a:hover { color: var(--primary-strong); }
.footer-img {
  position: absolute;
  left: 50%;
  top: 0;
  width: clamp(3rem, 5vw, 4.2rem);
  height: auto;
  transform: translateX(-50%);
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  display: block;
  pointer-events: none;
}



/* Editable manifest fields */
.edit-field { border: 2px solid var(--line); border-radius: 8px;
              padding: .4rem .52rem; font-size: .8rem; width: 100%;
              color: var(--ink); background: #fff; font-family: inherit;
              box-shadow: inset 0 1px 1px rgba(16,24,40,.02); }
.edit-field:focus { outline: 2px solid rgba(88,44,131,.14); border-color: var(--primary); }
select.edit-field { background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23582c83'/%3E%3C/svg%3E") no-repeat right .55rem center / 8px;
                    -webkit-appearance: none; appearance: none; padding-right: 1.4rem; }
.edit-field-sm { font-size: .75rem; }
input[type=checkbox].include-cb { width: 16px; height: 16px;
                                   accent-color: var(--primary); cursor: pointer; }

/* Agency pill selector */
.agency-bar { display: flex; gap: .3rem; flex-wrap: wrap; margin: .6rem 0 .4rem; }
.agency-pill { display: inline-flex; align-items: center; gap: .3rem;
               padding: .24rem .62rem; border-radius: 8px; font-size: .76rem;
               font-weight: 800; cursor: pointer; border: 2px solid transparent;
               font-family: "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif;
               background: #eef1f6; color: var(--muted); transition: all .15s; }
.agency-pill:hover { border-color: rgba(88,44,131,.12); background: var(--primary-mist); }
.agency-pill input[type=radio] { display: none; }
.agency-pill.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.agency-label { font-size: .8rem; font-weight: 800; color: var(--primary-deep); }

/* NIH credential warning */
.nih-cred-warn { font-size: .72rem; color: var(--danger); font-weight: 700;
                 margin-top: .2rem; display: flex; align-items: center; gap: .25rem; }

/* Save manifest bar */
.manifest-save-bar { display: flex; align-items: center; gap: .8rem;
                     flex-wrap: wrap; padding: .5rem 0 .7rem; }
.manifest-save-actions { display: inline-flex; align-items: center; gap: .45rem; flex-wrap: wrap; }
.manifest-save-note { font-size: .75rem; color: var(--muted); }
.email-edit-label { display: block; margin-top: .38rem; font-size: .68rem; font-weight: 800;
                    color: var(--primary-deep); text-transform: uppercase; letter-spacing: .04em; }

/* Contact picker modal */
.contact-modal-shell[hidden] { display: none !important; }
.contact-modal-shell { position: fixed; inset: 0; z-index: 70; }
.contact-modal-backdrop { position: absolute; inset: 0; background: rgba(24, 16, 34, .62); backdrop-filter: blur(2px); }
.contact-modal { position: relative; width: min(42rem, calc(100vw - 1.5rem)); margin: calc(8vh + 300px) auto 0;
                 background: linear-gradient(180deg, #fff, #f8f4ff); border: 3px solid rgba(88,44,131,.24);
                 border-radius: 14px; box-shadow: 0 18px 48px rgba(24,16,34,.34); overflow: hidden; }
.contact-modal-header { display: flex; align-items: flex-start; justify-content: space-between; gap: .8rem;
                        padding: .95rem 1rem .55rem; border-bottom: 1px solid rgba(88,44,131,.1); }
.contact-modal-title { margin: 0; font-size: .96rem; color: var(--primary-deep); }
.contact-modal-subtitle { margin: .22rem 0 0; font-size: .75rem; color: var(--muted); }
.contact-modal-close { min-width: 2.2rem; padding-inline: .4rem; }
.contact-modal-body { padding: .85rem 1rem 1rem; }
.contact-picker-composer { display: flex; flex-wrap: wrap; gap: .35rem; align-items: center;
                           min-height: 3rem; padding: .45rem; border: 2px solid var(--line);
                           border-radius: 10px; background: #fff; }
.contact-picker-composer:focus-within { border-color: var(--primary); outline: 2px solid rgba(88,44,131,.14); }
.contact-picker-chip { display: inline-flex; align-items: center; gap: .35rem; max-width: 100%;
                       padding: .24rem .45rem; background: var(--primary-mist); color: var(--primary-deep);
                       border: 1px solid rgba(88,44,131,.12); border-radius: 999px; font-size: .73rem; font-weight: 700; }
.contact-picker-chip-text { display: inline-flex; gap: .25rem; min-width: 0; }
.contact-picker-chip-name, .contact-picker-chip-email { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.contact-picker-chip-remove { border: 0; background: transparent; color: inherit; cursor: pointer; padding: 0; font-size: .9rem; line-height: 1; }
.contact-picker-input { flex: 1 1 12rem; min-width: 10rem; border: 0; outline: 0; font: inherit; color: var(--ink); padding: .2rem .25rem; background: transparent; }
.contact-picker-results { margin-top: .55rem; border: 2px solid rgba(88,44,131,.1); border-radius: 10px;
                          background: #fff; max-height: 17rem; overflow: auto; }
.contact-picker-empty { padding: .7rem .85rem; font-size: .76rem; color: var(--muted); }
.contact-picker-option { display: block; width: 100%; border: 0; text-align: left; cursor: pointer;
                         padding: .58rem .75rem; background: #fff; border-bottom: 1px solid rgba(88,44,131,.08); }
.contact-picker-option:last-child { border-bottom: 0; }
.contact-picker-option:hover, .contact-picker-option.active { background: rgba(88,44,131,.06); }
.contact-picker-option-name { font-size: .8rem; font-weight: 800; color: var(--ink); }
.contact-picker-option-email { font-size: .74rem; color: var(--primary-deep); margin-top: .08rem; }
.contact-picker-option-meta { font-size: .71rem; color: var(--muted); margin-top: .1rem; }
.contact-modal-footer { display: flex; align-items: center; justify-content: space-between; gap: .8rem;
                        flex-wrap: wrap; padding: .75rem 1rem 1rem; border-top: 1px solid rgba(88,44,131,.1); }

/* Header refresh toggle */
.refresh-toggle-btn { --pixel-button-border: var(--pixel-button-border-slate); --button-fill: linear-gradient(180deg, rgba(255,255,255,.16), rgba(255,255,255,.03)); font-family: "PixeloidSans", "Trebuchet MS", "Segoe UI", Arial, sans-serif;
                      color: rgba(255,255,255,.88);
                      padding: .35rem .9rem; font-size: .75rem; font-weight: 700;
                      border-radius: 6px; cursor: pointer; transition: all .15s; box-shadow: 0 2px 0 rgba(24,14,36,.18); }
.refresh-toggle-btn:hover { --button-fill: linear-gradient(180deg, rgba(255,255,255,.22), rgba(255,255,255,.08)); color: #fff; }
.refresh-toggle-btn.paused { --button-fill: linear-gradient(180deg, rgba(255,209,0,.22), rgba(255,209,0,.08)); color: var(--accent); box-shadow: 0 2px 0 rgba(24,14,36,.18), 0 0 0 1px rgba(255,209,0,.28); }

@media (max-width: 980px) {
  header { padding: .9rem 1rem; flex-wrap: wrap; }
  header .header-brand { flex-wrap: wrap; }
  main { padding: 0 .85rem 1rem; }
  .row2 { grid-template-columns: 1fr; }
  .tab-bar { display: flex; width: 100%; overflow-x: auto; }
  header .tab-bar { margin-left: 0; order: 3; }
  .header-actions { width: 100%; align-items: flex-end; }
  .contact-modal { width: calc(100vw - 1rem); margin-top: min(calc(4vh + 120px), 28vh); }
}
"""

# ── JavaScript ────────────────────────────────────────────────────────────────

_JS = """
(function() {
  var REFRESH_INTERVAL_MS = 10000;
  var refreshTimer = null;
  var refreshInFlight = false;
  var manualRefreshPaused = window.sessionStorage.getItem('rrtard-refresh-paused') === '1';

  function isEditingForm() {
    var active = document.activeElement;
    if (!active) return false;
    if (!active.closest('form')) return false;
    return active.tagName === 'INPUT' ||
           active.tagName === 'SELECT' ||
           active.tagName === 'TEXTAREA' ||
           active.isContentEditable;
  }

  function refreshButton() {
    return document.getElementById('refresh-toggle');
  }

  function syncRefreshButton() {
    var btn = refreshButton();
    if (!btn) return;
    if (manualRefreshPaused) {
      btn.innerHTML = '__PLAY_ICON__Resume';
      btn.classList.add('paused');
    } else {
      btn.innerHTML = '__PAUSE_ICON__Pause';
      btn.classList.remove('paused');
    }
  }

  function scheduleRefresh() {
    clearTimeout(refreshTimer);
    if (!manualRefreshPaused) {
      refreshTimer = setTimeout(function() {
        refreshView();
      }, REFRESH_INTERVAL_MS);
    }
  }

  function refreshView(options) {
    options = options || {};
    clearTimeout(refreshTimer);
    if (refreshInFlight) {
      scheduleRefresh();
      return Promise.resolve(false);
    }
    if (manualRefreshPaused && !options.force) {
      return Promise.resolve(false);
    }
    if (!options.force && (document.hidden || isEditingForm())) {
      scheduleRefresh();
      return Promise.resolve(false);
    }
    refreshInFlight = true;
    return fetch(window.location.pathname + window.location.search, {
      headers: {'X-Requested-With': 'soft-refresh'}
    })
      .then(function(resp) {
        if (!resp.ok) {
          throw new Error('refresh failed');
        }
        return resp.text();
      })
      .then(function(text) {
        var parser = new DOMParser();
        var nextDoc = parser.parseFromString(text, 'text/html');
        var currentMain = document.getElementById('app-main');
        var nextMain = nextDoc.getElementById('app-main');
        if (!currentMain || !nextMain) {
          throw new Error('missing main container');
        }
        if (!options.force && nextMain.innerHTML === currentMain.innerHTML) {
          return false;
        }
        currentMain.innerHTML = nextMain.innerHTML;
        if (nextDoc.title) {
          document.title = nextDoc.title;
        }
        hydratePage();
        return true;
      })
      .catch(function() {
        if (options.force) {
          window.location.reload();
        }
        return false;
      })
      .finally(function() {
        refreshInFlight = false;
        syncRefreshButton();
        scheduleRefresh();
      });
  }

  // ── Drop zone upload ────────────────────────────────────────────────────────
  function uploadFiles(zone, uploadUrl, files) {
    var pdfs = Array.prototype.filter.call(files, function(f) {
      return f.name.toLowerCase().endsWith('.pdf');
    });
    if (!pdfs.length) { alert('Please drop PDF files only.'); return; }
    var fd = new FormData();
    pdfs.forEach(function(f) { fd.append('pdf', f, f.name); });
    zone.innerHTML = '<div class="dz-icon">__CLOCK_ICON__</div><p>Uploading ' + pdfs.length + ' file(s)…</p>';
    fetch(uploadUrl, { method: 'POST', body: fd })
      .then(function() { return refreshView({force: true}); })
      .catch(function() { window.location.reload(); });
  }

  function bindDropZone() {
    var zone = document.getElementById('drop-zone');
    if (!zone || zone.dataset.bound === '1') return;
    var input = document.getElementById('pdf-file-input');
    if (!input) return;
    var uploadUrl = zone.getAttribute('data-upload-url') || '/upload-pdf';
    zone.dataset.bound = '1';
    zone.addEventListener('click', function() {
      input.click();
    });
    zone.addEventListener('dragover', function(e) {
      e.preventDefault();
      zone.classList.add('drag-over');
    });
    zone.addEventListener('dragleave', function() {
      zone.classList.remove('drag-over');
    });
    zone.addEventListener('drop', function(e) {
      e.preventDefault();
      zone.classList.remove('drag-over');
      uploadFiles(zone, uploadUrl, e.dataTransfer.files);
    });
    input.addEventListener('change', function(e) {
      uploadFiles(zone, uploadUrl, e.target.files);
    });
  }

  // ── Agency pills ─────────────────────────────────────────────────────────────
  function bindAgencyPills() {
    document.querySelectorAll('#agency-bar .agency-pill input[type=radio]').forEach(function(radio) {
      if (radio.dataset.bound === '1') return;
      radio.dataset.bound = '1';
      radio.addEventListener('change', function() {
        fetch('/set-agency', {
          method: 'POST',
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: 'agency=' + encodeURIComponent(radio.value)
        }).then(function() { return refreshView({force: true}); });
      });
    });
  }

  // ── Role select: show/hide "Other" text field ─────────────────────────────
  function bindRoleToggles() {
    document.querySelectorAll('select[name^=role_]').forEach(function(sel) {
      var other = document.querySelector('[data-other-for="' + sel.name + '"]');
      if (!other) return;
      function toggle() {
        var v = sel.value;
        other.style.display = (v.indexOf('Other') !== -1 || v.indexOf('specify') !== -1) ? '' : 'none';
      }
      if (sel.dataset.bound !== '1') {
        sel.dataset.bound = '1';
        sel.addEventListener('change', toggle);
      }
      toggle();
    });
  }

  // ── Contact picker modal ───────────────────────────────────────────────────
  function bindContactPicker() {
    var form = document.getElementById('manifest-form');
    if (!form || form.dataset.contactPickerBound === '1') return;
    form.dataset.contactPickerBound = '1';

    var modal = document.getElementById('contact-picker-modal');
    var hiddenInput = document.getElementById('add-contacts-input');
    var queryInput = document.getElementById('contact-picker-input');
    var chipsNode = document.getElementById('contact-picker-chips');
    var resultsNode = document.getElementById('contact-picker-results');
    var addBtn = document.getElementById('contact-picker-add');
    if (!modal || !hiddenInput || !queryInput || !chipsNode || !resultsNode || !addBtn) return;

    var contacts = [];
    var contactsLoaded = false;
    var contactsLoading = false;
    var contactsError = '';
    var directoryUrl = form.getAttribute('data-contact-directory-url') || '/contact-directory';

    var existingEmails = {};
    try {
      JSON.parse(form.getAttribute('data-existing-emails') || '[]').forEach(function(email) {
        existingEmails[String(email || '').toLowerCase()] = true;
      });
    } catch (err) {}

    var selected = [];
    var activeIndex = -1;

    function loadContacts() {
      if (contactsLoaded || contactsLoading) return Promise.resolve(contacts);
      contactsLoading = true;
      contactsError = '';
      resultsNode.innerHTML = '<div class="contact-picker-empty">Loading contacts…</div>';
      return fetch(directoryUrl, {
        headers: {'X-Requested-With': 'contact-picker'}
      })
        .then(function(resp) {
          if (!resp.ok) throw new Error('failed to load contacts');
          return resp.json();
        })
        .then(function(payload) {
          contacts = Array.isArray(payload) ? payload : [];
          contactsLoaded = true;
          contactsLoading = false;
          render();
          return contacts;
        })
        .catch(function() {
          contacts = [];
          contactsLoading = false;
          contactsError = 'Unable to load contacts right now.';
          render();
          return contacts;
        });
    }

    function selectedEmails() {
      var lookup = {};
      selected.forEach(function(contact) {
        lookup[String(contact.email || '').toLowerCase()] = true;
      });
      return lookup;
    }

    function filterContacts() {
      var taken = selectedEmails();
      var query = String(queryInput.value || '').trim().toLowerCase();
      return contacts.filter(function(contact) {
        var email = String(contact.email || '').toLowerCase();
        if (!email || existingEmails[email] || taken[email]) return false;
        if (!query) return true;
        var haystack = [
          contact.fullName || '',
          contact.email || '',
          contact.title || '',
          contact.department || ''
        ].join(' ').toLowerCase();
        return haystack.indexOf(query) !== -1;
      }).slice(0, 8);
    }

    function renderChips() {
      chipsNode.innerHTML = '';
      selected.forEach(function(contact) {
        var chip = document.createElement('span');
        chip.className = 'contact-picker-chip';
        chip.innerHTML =
          '<span class="contact-picker-chip-text">' +
            '<span class="contact-picker-chip-name"></span>' +
            '<span class="contact-picker-chip-email"></span>' +
          '</span>' +
          '<button type="button" class="contact-picker-chip-remove" aria-label="Remove contact">&times;</button>';
        chip.querySelector('.contact-picker-chip-name').textContent = contact.fullName || contact.email;
        chip.querySelector('.contact-picker-chip-email').textContent = contact.email || '';
        chip.querySelector('.contact-picker-chip-remove').addEventListener('click', function() {
          selected = selected.filter(function(item) { return item.email !== contact.email; });
          render();
          queryInput.focus();
        });
        chipsNode.appendChild(chip);
      });
    }

    function addSelectedContact(contact) {
      if (!contact || !contact.email) return;
      var email = String(contact.email).toLowerCase();
      if (existingEmails[email] || selectedEmails()[email]) return;
      selected.push(contact);
      queryInput.value = '';
      activeIndex = -1;
      render();
      queryInput.focus();
    }

    function renderResults() {
      if (contactsLoading) {
        resultsNode.innerHTML = '<div class="contact-picker-empty">Loading contacts…</div>';
        return;
      }
      if (contactsError) {
        resultsNode.innerHTML = '<div class="contact-picker-empty">' + contactsError + '</div>';
        return;
      }
      var matches = filterContacts();
      if (activeIndex >= matches.length) activeIndex = matches.length - 1;
      resultsNode.innerHTML = '';
      if (!matches.length) {
        var empty = document.createElement('div');
        empty.className = 'contact-picker-empty';
        empty.textContent = contacts.length ? 'No matching contacts.' : 'No contacts loaded from contacts.json.';
        resultsNode.appendChild(empty);
        return;
      }
      matches.forEach(function(contact, index) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'contact-picker-option' + (index === activeIndex ? ' active' : '');
        btn.innerHTML =
          '<div class="contact-picker-option-name"></div>' +
          '<div class="contact-picker-option-email"></div>' +
          '<div class="contact-picker-option-meta"></div>';
        btn.querySelector('.contact-picker-option-name').textContent = contact.fullName || contact.email;
        btn.querySelector('.contact-picker-option-email').textContent = contact.email || '';
        btn.querySelector('.contact-picker-option-meta').textContent =
          [contact.title || '', contact.department || ''].filter(Boolean).join(' · ') || 'Tennessee Technological University';
        btn.addEventListener('click', function() {
          addSelectedContact(contact);
        });
        resultsNode.appendChild(btn);
      });
    }

    function render() {
      renderChips();
      renderResults();
      addBtn.disabled = selected.length === 0;
      addBtn.className = selected.length ? 'btn-primary btn-sm' : 'btn-disabled btn-sm';
    }

    function openModal() {
      modal.hidden = false;
      document.body.style.overflow = 'hidden';
      render();
      loadContacts();
      window.setTimeout(function() { queryInput.focus(); }, 20);
    }

    function closeModal() {
      modal.hidden = true;
      document.body.style.overflow = '';
      queryInput.value = '';
      activeIndex = -1;
      render();
    }

    document.querySelectorAll('[data-open-contact-picker]').forEach(function(btn) {
      if (btn.dataset.bound === '1') return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', openModal);
    });

    modal.querySelectorAll('[data-close-contact-picker]').forEach(function(node) {
      if (node.dataset.bound === '1') return;
      node.dataset.bound = '1';
      node.addEventListener('click', closeModal);
    });

    queryInput.addEventListener('input', function() {
      activeIndex = 0;
      renderResults();
    });
    queryInput.addEventListener('keydown', function(event) {
      var matches = filterContacts();
      if (event.key === 'Backspace' && !queryInput.value && selected.length) {
        selected.pop();
        render();
        return;
      }
      if (event.key === 'Escape') {
        closeModal();
        return;
      }
      if (!matches.length) return;
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeIndex = Math.min(activeIndex + 1, matches.length - 1);
        renderResults();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        renderResults();
      } else if (event.key === 'Enter') {
        event.preventDefault();
        addSelectedContact(matches[Math.max(activeIndex, 0)]);
      }
    });

    addBtn.addEventListener('click', function() {
      if (!selected.length) return;
      hiddenInput.value = JSON.stringify(selected.map(function(contact) { return contact.email; }));
      form.submit();
    });

    render();
  }

  function hydratePage() {
    bindDropZone();
    bindAgencyPills();
    bindRoleToggles();
    bindContactPicker();
    syncRefreshButton();
  }

  window.toggleRefresh = function() {
    manualRefreshPaused = !manualRefreshPaused;
    window.sessionStorage.setItem('rrtard-refresh-paused', manualRefreshPaused ? '1' : '0');
    syncRefreshButton();
    scheduleRefresh();
  };

  hydratePage();
  scheduleRefresh();

  // ── Tab switching ───────────────────────────────────────────────────────────
  window.switchTab = function(tab) {
    // Persist tab choice across refreshes
    var url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    window.location.replace(url.toString());
  };
})();
"""

# ── HTML template ─────────────────────────────────────────────────────────────

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{tab_title}</title>
<style>{css}</style>
</head>
<body>
<header>
  <div class="header-brand">
    <img class="header-badge" src="/img/pixelT.png" alt="R and R TARD badge">
    <div class="header-brand-copy">
      <h1>R&amp;R<span class="accent">TAR</span></h1>
      <span class="sub">R&amp;R Tool-Assisted<br>Re-entry Dashboard</span>
    </div>
  </div>
  <div class="tab-bar">
    <button class="tab-btn {kp_tab_active}" onclick="switchTab('keyperson')">{people_icon}Key Person</button>
    <button class="tab-btn {budget_tab_active}" onclick="switchTab('budget')">{budget_icon}Budget</button>
    <button class="tab-btn {ps_tab_active}" onclick="switchTab('performance-site')">{pin_icon}Performance Site</button>
  </div>
  <div class="header-actions">
    <button id="refresh-toggle" onclick="toggleRefresh()" class="refresh-toggle-btn header-utility-btn">{pause_icon}Pause</button>
    {header_reset_btn}
  </div>
</header>
<main id="app-main">
  {tab_content}
  <div class="footer-note-wrap">
    <img class="footer-img" src="/img/t_spin.gif" alt="">
    <p class="refresh-note">Pipeline steps run in the background. Editing the manifest pauses auto-refresh.</p>
  </div>
</main>
<script>{js}</script>
</body>
</html>"""

_KP_TAB_CONTENT = """
  <div class="row2">
    <!-- Pipeline Controls -->
    <div class="card">
      <h2>{automation_icon}Pipeline</h2>
      <ul class="steps">{steps_html}</ul>
      <div class="automate-row">
        {automate_btn}
      </div>
      <div class="chrome-box">
        {chrome_btn}
        <span class="chrome-info">{chrome_status}</span>
      </div>
    </div>
    <!-- Upload + PDF list -->
    <div class="card">
      <h2>{folder_icon}Input PDFs &nbsp;<span class="badge {pdf_badge}">{pdf_count} file{pdf_plural}</span></h2>
      <div id="drop-zone" class="drop-zone" data-upload-url="/upload-pdf">
        <input type="file" id="pdf-file-input" accept=".pdf" multiple>
        <div class="dz-icon">{upload_icon}</div>
        <p><strong>Drop Key Person PDFs here</strong> or click to browse</p>
        <p style="font-size:.72rem;margin-top:.2rem">Adds to input-pdfs/ automatically</p>
      </div>
      {pdf_table}
    </div>
  </div>
  <!-- Persons manifest -->
  <div class="card" style="margin-bottom:1.2rem">
    <h2>{manifest_icon}Import Manifest
      &nbsp;<span class="badge {manifest_badge}">{manifest_count} person{manifest_plural} included</span>
      {warn_badge}
    </h2>
    <div class="manifest-wrap">{manifest_table}</div>
  </div>
"""

_BUDGET_TAB_CONTENT = """
  <div class="row2">
    <!-- Budget Pipeline Controls -->
    <div class="card">
      <h2>{automation_icon}Budget Pipeline</h2>
      <ul class="steps">{budget_steps_html}</ul>
      <div class="automate-row">
        {budget_automate_btn}
      </div>
      <div class="chrome-box">
        {chrome_btn}
        <span class="chrome-info">{chrome_status}</span>
      </div>
    </div>
    <!-- Budget PDF upload + list -->
    <div class="card">
      <h2>{folder_icon}Budget PDFs &nbsp;<span class="badge {budget_pdf_badge}">{budget_pdf_count} file{budget_pdf_plural}</span></h2>
      <div id="drop-zone" class="drop-zone" data-upload-url="/upload-budget-pdf">
        <input type="file" id="pdf-file-input" accept=".pdf" multiple>
        <div class="dz-icon">{upload_icon}</div>
        <p><strong>Drop Budget PDFs here</strong> or click to browse</p>
        <p style="font-size:.72rem;margin-top:.2rem">Adds to input-budget-pdfs/ automatically</p>
      </div>
      {budget_pdf_table}
    </div>
  </div>
  <!-- Budget manifest -->
  <div class="card" style="margin-bottom:1.2rem">
    <h2>{budget_icon}Budget Manifest
      &nbsp;<span class="badge {budget_manifest_badge}">{budget_manifest_count} source{budget_manifest_plural}</span>
    </h2>
    {budget_manifest_html}
  </div>
"""

_PERFORMANCE_SITE_TAB_CONTENT = """
  <div class="row2">
    <div class="card">
      <h2>{automation_icon}Performance Site Pipeline</h2>
      <ul class="steps">{ps_steps_html}</ul>
      <div class="automate-row">
        {ps_automate_btn}
      </div>
      <div class="chrome-box">
        {chrome_btn}
        <span class="chrome-info">{chrome_status}</span>
      </div>
    </div>
    <div class="card">
      <h2>{folder_icon}Performance Site PDFs &nbsp;<span class="badge {ps_pdf_badge}">{ps_pdf_count} file{ps_pdf_plural}</span></h2>
      <div id="drop-zone" class="drop-zone" data-upload-url="/upload-performance-site-pdf">
        <input type="file" id="pdf-file-input" accept=".pdf" multiple>
        <div class="dz-icon">{upload_icon}</div>
        <p><strong>Drop Performance Site PDFs here</strong> or click to browse</p>
        <p style="font-size:.72rem;margin-top:.2rem">Adds to input-performance-site-pdfs/ automatically</p>
      </div>
      {ps_pdf_table}
    </div>
  </div>
  <div class="card" style="margin-bottom:1.2rem">
    <h2>{pin_icon}Performance Site Manifest
      &nbsp;<span class="badge {ps_manifest_badge}">{ps_manifest_count} source{ps_manifest_plural}</span>
    </h2>
    {ps_manifest_html}
  </div>
"""


# ── rendering helpers ─────────────────────────────────────────────────────────

def _agency_bar_html(current: str) -> str:
    pills = []
    for val, label in _AGENCIES:
        active = "active" if val == current else ""
        pills.append(
            f'<label class="agency-pill {active}" title="{html.escape(label)}">'
            f'<input type="radio" name="_agency_pill" value="{val}">'
            f'{html.escape(label)}</label>'
        )
    return (
        '<span class="agency-label">Agency:</span>'
        '<div class="agency-bar" id="agency-bar">' + "".join(pills) + "</div>"
    )


def _steps_html(steps: list[dict], agency: str) -> str:
    out = []
    for s in steps:
        if s["done"]:
            badge = f'<span class="badge done step-badge step-state" aria-label="done">{_icon("check", classes="icon-status")}</span>'
        else:
            badge = '<span class="badge pend step-badge step-state">pending</span>'

        enabled = s.get("enabled", True)
        if enabled:
            run_btn = (
                f'<form method="POST" action="/run-step" class="step-action" style="margin:0">'
                f'<input type="hidden" name="step" value="{s["cmd"]}">'
                f'<button type="submit" class="btn-run step-btn">{_icon("play", classes="icon-btn")}Run</button>'
                f'</form>'
            )
        else:
            run_btn = (
                '<span class="step-action">'
                f'<button type="button" class="btn-disabled step-btn" disabled>{_icon("play", classes="icon-btn")}Run</button>'
                '</span>'
            )

        hint = f'<span class="step-hint">{html.escape(s["hint"])}</span>'
        out.append(
            f'<li>{run_btn}<strong class="step-name">{html.escape(s["name"])}</strong>{badge}{hint}</li>'
        )
    agency_section = _agency_bar_html(agency)
    return "\n".join(out) + f'\n<li style="margin-top:.6rem;display:flex;flex-direction:column;align-items:flex-start">{agency_section}</li>'


def _pdf_table(input_pdfs: list[Path], extract_map: dict[str, dict]) -> str:
    if not input_pdfs:
        return '<p style="color:#aaa;font-size:.83rem;text-align:center;padding:.5rem 0">No PDFs yet — drop some above</p>'
    rows = []
    for p in input_pdfs:
        rec = extract_map.get(p.name)
        if rec:
            pdpi = rec.get("pdpi_count", 0)
            kp = rec.get("key_person_count", 0)
            atts = len([a for a in rec.get("attachments", []) if a.get("path")])
            status = (
            f'<span class="badge ok">extracted</span> '
                f'<span class="sub-info">{pdpi} PDPI &nbsp; {kp} KeyPerson &nbsp; {atts} files</span>'
            )
        else:
            status = '<span class="badge pend">not extracted</span>'
        size_kb = p.stat().st_size // 1024
        remove_btn = (
            f'<form method="POST" action="/remove-pdf" style="margin:0">'
            f'<input type="hidden" name="filename" value="{html.escape(p.name)}">'
            f'<button type="submit" class="btn-danger btn-sm" '
            f'onclick="return confirm(\'Remove {html.escape(p.name)} from input-pdfs/?\')">'
            f'{_icon("close", classes="icon-btn")}</button>'
            f'</form>'
        )
        rows.append(
            f"<tr>"
            f"<td><strong style='font-size:.83rem'>{html.escape(p.name)}</strong></td>"
            f"<td class='sub-dim'>{size_kb} KB</td>"
            f"<td>{status}</td>"
            f"<td style='text-align:center'>{remove_btn}</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>File</th><th>Size</th><th>Status</th><th></th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _manifest_table(manifest: list[dict], agency: str) -> str:
    existing_emails = [
        _clean_ws(str((entry.get("person") or {}).get("email") or "")).lower()
        for entry in manifest
        if _clean_ws(str((entry.get("person") or {}).get("email") or ""))
    ]

    rows = []
    for i, e in enumerate(manifest):
        p = e["person"]
        excl = e.get("exclude", False)

        name_parts = [
            p.get("prefix", ""), p.get("first_name", ""),
            p.get("middle_name", ""), p.get("last_name", ""), p.get("suffix", ""),
        ]
        full_name = html.escape(" ".join(x for x in name_parts if x).strip() or "—")
        src_pdf = html.escape(Path(e.get("source_pdf", "")).name)
        src_el = e.get("source_element", "")
        src_idx = e.get("source_index", 0)
        if src_el == "KeyPerson":
            src_label = html.escape(f"KeyPerson[{src_idx}]")
        elif src_el == "ContactDirectory":
            src_label = "Address Book"
        elif src_el == "AttachmentFallback":
            src_label = "Attachment"
        else:
            src_label = "PDPI"

        # Include checkbox (hidden-field trick so unchecked = 0)
        chk = "checked" if not excl else ""
        include_cell = (
            f'<input type="hidden" name="include_{i}" value="0">'
            f'<input type="checkbox" name="include_{i}" value="1" {chk} class="include-cb">'
        )

        # Contact (read-only display)
        raw_email = p.get("email", "") or ""
        email_val = html.escape(raw_email)
        phone_val = html.escape(p.get("phone", "") or "")
        incomplete_name = (
            not (p.get("first_name", "") or "").strip()
            or not (p.get("last_name", "") or "").strip()
            or any("Name is incomplete" in w for w in e.get("validation", {}).get("warnings", []))
        )
        contact_parts = []
        if email_val:
            contact_parts.append(f'<a href="mailto:{email_val}" class="sub-info">{email_val}</a>')
        if phone_val:
            contact_parts.append(f'<span class="sub-dim">{phone_val}</span>')
        if incomplete_name or not raw_email.strip():
            contact_parts.append(
                f'<label class="email-edit-label" for="email_{i}">Email</label>'
                f'<input type="email" id="email_{i}" name="email_{i}" class="edit-field edit-field-sm"'
                f' placeholder="faculty@tntech.edu" value="{html.escape(raw_email)}">'
            )
        contact_cell = "<br>".join(contact_parts) or '<span class="sub-dim">—</span>'

        # Organization — editable
        org_val = p.get("organization_name", "") or ""
        dept = html.escape(p.get("department", "") or "")
        div_val = html.escape(p.get("division", "") or "")
        org_cell = (
            f'<input type="text" name="org_{i}" class="edit-field"'
            f' value="{html.escape(org_val)}">'
        )
        if dept or div_val:
            sub = " · ".join(x for x in (dept, div_val) if x)
            org_cell += f'<div class="sub-dim" style="margin-top:.2rem">{sub}</div>'

        # Role — editable select
        current_role = p.get("project_role", "") or ""
        opts = "".join(
            f'<option value="{html.escape(r)}"{"selected" if r == current_role else ""}>'
            f'{html.escape(r) if r else "— select role —"}</option>'
            for r in _RR_PROJECT_ROLES
        )
        role_cell = f'<select name="role_{i}" class="edit-field">{opts}</select>'
        # Other role text field — always rendered, shown/hidden via JS
        other_val = html.escape(p.get("other_project_role_category", "") or "")
        role_cell += (
            f'<input type="text" name="other_role_{i}" class="edit-field edit-field-sm"'
            f' placeholder="Specify other role…" value="{other_val}"'
            f' style="margin-top:.25rem;{"display:none" if "Other" not in current_role and "specify" not in current_role.lower() else ""}"'
            f' data-other-for="role_{i}">'
        )
        # Credential — editable
        cred_val = p.get("credential", "") or ""
        role_cell += (
            f'<input type="text" name="credential_{i}" class="edit-field mono edit-field-sm"'
            f' placeholder="eRA Commons ID…" value="{html.escape(cred_val)}"'
            f' style="margin-top:.25rem">'
        )
        if agency == "NIH_PHS" and not cred_val:
            role_cell += f'<div class="nih-cred-warn">{_icon("warning", classes="icon-status")}eRA Commons ID required for NIH</div>'

        # Degree (read-only)
        dt = html.escape(p.get("degree_type", "") or "")
        dy = html.escape(p.get("degree_year", "") or "")
        degree_cell = f'<span class="sub-info">{(dt + " " + dy).strip()}</span>' if (dt or dy) else '<span class="sub-dim">—</span>'

        # Location (read-only)
        addr = p.get("address", {}) or {}
        city = html.escape(addr.get("city", "") or "")
        state = html.escape(addr.get("state", "") or addr.get("province", "") or "")
        country = html.escape(addr.get("country", "") or "")
        loc_parts = [x for x in (city, state, country) if x]
        loc_cell = f'<span class="sub-info">{", ".join(loc_parts)}</span>' if loc_parts else '<span class="sub-dim">—</span>'

        # Attachments (read-only)
        bio = e.get("attachments", {}).get("biosketch", {}) or {}
        sup = e.get("attachments", {}).get("current_pending_support", {}) or {}
        bio_path = bio.get("path")
        sup_path = sup.get("path")
        bio_name = html.escape(Path(bio_path).name) if bio_path else ""
        sup_name = html.escape(Path(sup_path).name) if sup_path else ""
        bio_line = (f'<span class="att-ok" title="{bio_name}">{_icon("check", classes="icon-status")} {bio_name}</span>'
                    if bio_path else f'<span class="att-miss">{_icon("close", classes="icon-status")} bio missing</span>')
        sup_line = (f'<span class="att-ok" title="{sup_name}">{_icon("check", classes="icon-status")} {sup_name}</span>'
                    if sup_path else '<span class="sub-dim">— no support</span>')
        att_cell = f"{bio_line}<br>{sup_line}"

        # Warnings — filter out agency-irrelevant ones when not NIH
        warnings = e.get("validation", {}).get("warnings", [])
        if agency != "NIH_PHS":
            warnings = [w for w in warnings if "NIH" not in w and "eRA" not in w]
        if warnings:
            items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
            warn_cell = f'<ul class="warn-list">{items}</ul>'
        else:
            warn_cell = '<span class="sub-dim">—</span>'

        rows.append(
            f"<tr>"
            f"<td style='text-align:center'>{include_cell}</td>"
            f"<td><span class='person-name'>{full_name}</span><br>"
            f"<span class='person-src'>{src_pdf} / {src_label}</span></td>"
            f"<td>{contact_cell}</td>"
            f"<td>{org_cell}</td>"
            f"<td>{role_cell}</td>"
            f"<td>{degree_cell}</td>"
            f"<td>{loc_cell}</td>"
            f"<td>{att_cell}</td>"
            f"<td>{warn_cell}</td>"
            f"</tr>"
        )

    save_btn = f'<button type="submit" class="btn-primary btn-sm">{_icon("save", classes="icon-btn")}Save Changes</button>'
    add_contacts_btn = (
        f'<button type="button" class="btn-success btn-sm" data-open-contact-picker>'
        f'{_icon("addressbook", classes="icon-btn")}Add from Contacts</button>'
    )
    content = (
        '<div class="kp-manifest"><table><thead><tr>'
        "<th>Incl.</th><th>Name</th><th>Contact</th><th>Organization</th>"
        "<th>Role / Credential</th><th>Degree</th><th>Location</th>"
        "<th>Attachments</th><th>Warnings</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    ) if manifest else (
        '<div style="padding:.9rem 0 1rem; display:flex; align-items:center; justify-content:center">'
        f'{add_contacts_btn}'
        '</div>'
    )
    top_bar = (
        f'<div class="manifest-save-bar"><span class="manifest-save-actions">{save_btn}{add_contacts_btn}</span>'
        f'<span class="manifest-save-note">Edits are written to import_manifest.json and used on the next automate run.</span>'
        f'</div>'
    ) if manifest else (
        f'<div class="manifest-save-bar"><span class="manifest-save-actions">{add_contacts_btn}</span>'
        f'<span class="manifest-save-note">Start a new manifest directly from contacts.json.</span>'
        f'</div>'
    )
    bottom_bar = (
        f'<div class="manifest-save-bar" style="padding-top:.6rem"><span class="manifest-save-actions">{save_btn}{add_contacts_btn}</span></div>'
        if manifest else ""
    )
    modal = (
        '<div id="contact-picker-modal" class="contact-modal-shell" hidden>'
        '  <div class="contact-modal-backdrop" data-close-contact-picker></div>'
        '  <div class="contact-modal" role="dialog" aria-modal="true" aria-labelledby="contact-picker-title">'
        '    <div class="contact-modal-header">'
        '      <div>'
        '        <h3 id="contact-picker-title" class="contact-modal-title">Add Faculty from Contacts</h3>'
        '        <p class="contact-modal-subtitle">Search by name, email, title, or department. Selected faculty are added together.</p>'
        '      </div>'
        f'      <button type="button" class="btn-warn btn-sm contact-modal-close" data-close-contact-picker>{_icon("close", classes="icon-btn")}</button>'
        '    </div>'
        '    <div class="contact-modal-body">'
        '      <div class="contact-picker-composer">'
        '        <div id="contact-picker-chips"></div>'
        '        <input type="text" id="contact-picker-input" class="contact-picker-input"'
        '         placeholder="Start typing a faculty name…" autocomplete="off">'
        '      </div>'
        '      <div id="contact-picker-results" class="contact-picker-results"></div>'
        '    </div>'
        '    <div class="contact-modal-footer">'
        '      <span class="manifest-save-note">Adding selected contacts submits this form and preserves your current edits.</span>'
        f'      <button type="button" id="contact-picker-add" class="btn-disabled btn-sm" disabled>{_icon("addressbook", classes="icon-btn")}Add Selected</button>'
        '    </div>'
        '  </div>'
        '</div>'
    )
    return (
        f'<form method="POST" action="/save-manifest" id="manifest-form"'
        f' data-existing-emails="{html.escape(json.dumps(existing_emails))}"'
        ' data-contact-directory-url="/contact-directory">'
        f'<input type="hidden" id="add-contacts-input" name="add_contacts" value="">'
        f'{top_bar}'
        f'{content}'
        f'{bottom_bar}'
        f'{modal}'
        f'</form>'
    )


def _budget_pdf_table(budget_pdfs: list[Path], extract_map: dict[str, dict]) -> str:
    if not budget_pdfs:
        return '<p style="color:#aaa;font-size:.83rem;text-align:center;padding:.5rem 0">No budget PDFs yet — drop some above</p>'
    rows = []
    for p in budget_pdfs:
        rec = extract_map.get(p.name)
        if rec:
            org = html.escape(rec.get("organization", ""))
            periods = rec.get("period_count", 0)
            atts = len([a for a in rec.get("attachments", []) if a.get("path")])
            status = (
                f'<span class="badge ok">extracted</span> '
                f'<span class="sub-info">{html.escape(org or "?")} &nbsp; {periods} period(s) &nbsp; {atts} file(s)</span>'
            )
        else:
            status = '<span class="badge pend">not extracted</span>'
        size_kb = p.stat().st_size // 1024
        remove_btn = (
            f'<form method="POST" action="/remove-budget-pdf" style="margin:0">'
            f'<input type="hidden" name="filename" value="{html.escape(p.name)}">'
            f'<button type="submit" class="btn-danger btn-sm" '
            f'onclick="return confirm(\'Remove {html.escape(p.name)} from input-budget-pdfs/?\')">'
            f'{_icon("close", classes="icon-btn")}</button>'
            f'</form>'
        )
        rows.append(
            f"<tr>"
            f"<td><strong style='font-size:.83rem'>{html.escape(p.name)}</strong></td>"
            f"<td class='sub-dim'>{size_kb} KB</td>"
            f"<td>{status}</td>"
            f"<td style='text-align:center'>{remove_btn}</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>File</th><th>Size</th><th>Status</th><th></th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _performance_site_pdf_table(ps_pdfs: list[Path], extract_map: dict[str, dict]) -> str:
    if not ps_pdfs:
        return '<p style="color:#aaa;font-size:.83rem;text-align:center;padding:.5rem 0">No performance site PDFs yet — drop some above</p>'
    rows = []
    for p in ps_pdfs:
        rec = extract_map.get(p.name)
        if rec:
            other_sites = rec.get("other_site_count", 0)
            atts = len([a for a in rec.get("attachments", []) if a.get("path")])
            status = (
                f'<span class="badge ok">extracted</span> '
                f'<span class="sub-info">{other_sites} other site(s) &nbsp; {atts} file(s)</span>'
            )
        else:
            status = '<span class="badge pend">not extracted</span>'
        size_kb = p.stat().st_size // 1024
        remove_btn = (
            f'<form method="POST" action="/remove-performance-site-pdf" style="margin:0">'
            f'<input type="hidden" name="filename" value="{html.escape(p.name)}">'
            f'<button type="submit" class="btn-danger btn-sm" '
            f'onclick="return confirm(\'Remove {html.escape(p.name)} from input-performance-site-pdfs/?\')">'
            f'{_icon("close", classes="icon-btn")}</button>'
            f'</form>'
        )
        rows.append(
            f"<tr>"
            f"<td><strong style='font-size:.83rem'>{html.escape(p.name)}</strong></td>"
            f"<td class='sub-dim'>{size_kb} KB</td>"
            f"<td>{status}</td>"
            f"<td style='text-align:center'>{remove_btn}</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>File</th><th>Size</th><th>Status</th><th></th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _budget_manifest_html(manifest: list[dict]) -> str:
    if not manifest:
        return '<p style="color:#aaa;font-size:.88rem">No budget manifest — run normalize-budget first.</p>'

    def _fmt(val: str | None) -> str:
        if not val:
            return "—"
        try:
            return f"${float(val):,.2f}"
        except (ValueError, TypeError):
            return str(val) or "—"

    def _mo(v: str | None) -> str:
        return v or ""

    def _sec_hdr(label: str) -> str:
        return (
            f'<tr class="bgt-sec-hdr"><td colspan="9">{html.escape(label)}</td></tr>'
        )

    def _data_row(
        name: str, role: str = "", cal: str = "", acad: str = "",
        summ: str = "", pers: str = "", salary: str = "",
        fringe: str = "", funds: str = "", indent: int = 0,
    ) -> str:
        pad = f"padding-left:{0.55 + indent * 0.8}rem"
        return (
            f'<tr class="bgt-data-row">'
            f'<td class="bgt-label" style="{pad}">{html.escape(str(name))}</td>'
            f'<td class="bgt-detail">{html.escape(str(role))}</td>'
            f'<td class="bgt-num">{html.escape(str(cal))}</td>'
            f'<td class="bgt-num">{html.escape(str(acad))}</td>'
            f'<td class="bgt-num">{html.escape(str(summ))}</td>'
            f'<td class="bgt-num">{html.escape(str(pers))}</td>'
            f'<td class="bgt-amt">{html.escape(str(salary))}</td>'
            f'<td class="bgt-amt">{html.escape(str(fringe))}</td>'
            f'<td class="bgt-amt bgt-funds">{html.escape(str(funds))}</td>'
            f'</tr>'
        )

    def _total_row(label: str, amount: str) -> str:
        return (
            f'<tr class="bgt-total-row">'
            f'<td colspan="8" class="bgt-total-label">{html.escape(str(label))}</td>'
            f'<td class="bgt-amt bgt-funds">{html.escape(str(amount))}</td>'
            f'</tr>'
        )

    def _subtotal_row(label: str, amount: str) -> str:
        return (
            f'<tr class="bgt-subtotal-row">'
            f'<td colspan="8" class="bgt-total-label">{html.escape(str(label))}</td>'
            f'<td class="bgt-amt bgt-funds">{html.escape(str(amount))}</td>'
            f'</tr>'
        )

    _THEAD = (
        '<thead><tr class="bgt-col-hdr">'
        '<th class="bgt-label">Description</th>'
        '<th class="bgt-detail">Role / Notes</th>'
        '<th class="bgt-num">Cal Mo</th>'
        '<th class="bgt-num">Acad Mo</th>'
        '<th class="bgt-num">Sum Mo</th>'
        '<th class="bgt-num"># Pers</th>'
        '<th class="bgt-amt">Req Salary</th>'
        '<th class="bgt-amt">Fringe</th>'
        '<th class="bgt-amt">Funds Req</th>'
        '</tr></thead>'
    )

    _B_STD_ROLES = [
        ("post_doc_associates",    "Post Doctoral Associates"),
        ("graduate_students",      "Graduate Students (Research Assistants)"),
        ("undergraduate_students", "Undergraduate Students"),
        ("secretarial_clerical",   "Secretarial / Clerical"),
    ]

    parts = []
    for entry in manifest:
        org      = entry.get("organization", {})
        just     = entry.get("budget_justification", {})
        just_name = Path(just.get("path") or "").name if just.get("path") else ""
        src      = entry.get("source_pdf", "?")
        org_name = html.escape(org.get("name", src))
        btype    = html.escape(org.get("budget_type", ""))
        uei      = html.escape(org.get("uei", ""))

        period_html_list = []
        for period in entry.get("periods", []):
            P     = period.get("period_index", "?")
            start = html.escape(period.get("start_date", ""))
            end   = html.escape(period.get("end_date", ""))
            rows: list[str] = []

            # Section A — Senior/Key Personnel
            rows.append(_sec_hdr("A. SENIOR / KEY PERSONNEL"))
            sec_a = period.get("section_a", {})
            for kp in sec_a.get("key_persons", []):
                rows.append(_data_row(
                    f'{kp.get("first_name","")  } {kp.get("last_name","")}'.strip(),
                    role=kp.get("project_role", ""),
                    cal=_mo(kp.get("calendar_months", "")),
                    acad=_mo(kp.get("academic_months", "")),
                    summ=_mo(kp.get("summer_months", "")),
                    salary=_fmt(kp.get("requested_salary", "")),
                    fringe=_fmt(kp.get("fringe_benefits", "")),
                    funds=_fmt(kp.get("funds_requested", "")),
                ))
            rows.append(_total_row("Section A Total", _fmt(sec_a.get("total", ""))))

            # Section B — Other Personnel
            rows.append(_sec_hdr("B. OTHER PERSONNEL"))
            sec_b = period.get("section_b", {})
            for key, label in _B_STD_ROLES:
                item = sec_b.get(key)
                if item and (item.get("funds_requested") or item.get("requested_salary")):
                    rows.append(_data_row(
                        label,
                        cal=_mo(item.get("calendar_months", "")),
                        acad=_mo(item.get("academic_months", "")),
                        summ=_mo(item.get("summer_months", "")),
                        pers=item.get("number_of_personnel", ""),
                        salary=_fmt(item.get("requested_salary", "")),
                        fringe=_fmt(item.get("fringe_benefits", "")),
                        funds=_fmt(item.get("funds_requested", "")),
                    ))
            for other in sec_b.get("other_personnel", []):
                rows.append(_data_row(
                    other.get("project_role", "Other Personnel"),
                    cal=_mo(other.get("calendar_months", "")),
                    acad=_mo(other.get("academic_months", "")),
                    summ=_mo(other.get("summer_months", "")),
                    pers=other.get("number_of_personnel", ""),
                    salary=_fmt(other.get("requested_salary", "")),
                    fringe=_fmt(other.get("fringe_benefits", "")),
                    funds=_fmt(other.get("funds_requested", "")),
                ))
            rows.append(_total_row("Section B Total", _fmt(sec_b.get("total_funds", ""))))

            # Section C — Equipment
            sec_c = period.get("section_c", {})
            if sec_c.get("items") or sec_c.get("total"):
                rows.append(_sec_hdr("C. EQUIPMENT"))
                for item in sec_c.get("items", []):
                    rows.append(_data_row(
                        item.get("description") or item.get("item", ""),
                        funds=_fmt(item.get("cost") or item.get("funds_requested", "")),
                    ))
                rows.append(_total_row("Section C Total", _fmt(sec_c.get("total", ""))))

            # Section D — Travel
            sec_d = period.get("section_d", {})
            if sec_d.get("total_travel_cost"):
                rows.append(_sec_hdr("D. TRAVEL"))
                rows.append(_data_row("Total Travel Costs", funds=_fmt(sec_d.get("total_travel_cost", ""))))

            # Section E — Participant / Trainee Support
            sec_e = period.get("section_e", {})
            if sec_e.get("total_cost") or sec_e.get("other_cost"):
                rows.append(_sec_hdr("E. PARTICIPANT / TRAINEE SUPPORT COSTS"))
                if sec_e.get("other_description") or sec_e.get("other_cost"):
                    rows.append(_data_row(
                        sec_e.get("other_description", "Other Costs"),
                        funds=_fmt(sec_e.get("other_cost", "")),
                    ))
                rows.append(_total_row("Section E Total", _fmt(sec_e.get("total_cost", ""))))

            # Section F — Other Direct Costs
            rows.append(_sec_hdr("F. OTHER DIRECT COSTS"))
            sec_f = period.get("section_f", {})
            if sec_f.get("materials_supplies"):
                rows.append(_data_row("Materials and Supplies", funds=_fmt(sec_f.get("materials_supplies", ""))))
            if sec_f.get("publication_costs"):
                rows.append(_data_row("Publication Costs", funds=_fmt(sec_f.get("publication_costs", ""))))
            if sec_f.get("consultant_services"):
                rows.append(_data_row("Consultant Services", funds=_fmt(sec_f.get("consultant_services", ""))))
            if sec_f.get("adp_computer_services"):
                rows.append(_data_row("ADP / Computer Services", funds=_fmt(sec_f.get("adp_computer_services", ""))))
            if sec_f.get("subawards_consortium_contractual_costs"):
                rows.append(_data_row("Subawards / Consortium / Contractual", funds=_fmt(sec_f.get("subawards_consortium_contractual_costs", ""))))
            if sec_f.get("equipment_facility_rental_user_fees"):
                rows.append(_data_row("Equipment / Facility Rental User Fees", funds=_fmt(sec_f.get("equipment_facility_rental_user_fees", ""))))
            if sec_f.get("alterations_renovations"):
                rows.append(_data_row("Alterations / Renovations", funds=_fmt(sec_f.get("alterations_renovations", ""))))
            for other in sec_f.get("other_items", []):
                rows.append(_data_row(other.get("description", "Other"), funds=_fmt(other.get("cost", ""))))
            rows.append(_total_row("Section F Total", _fmt(sec_f.get("total", ""))))

            # Section G — Total Direct Costs
            rows.append(_subtotal_row(
                "G. TOTAL DIRECT COSTS (A – F)",
                _fmt(period.get("direct_costs", "")),
            ))

            # Section H — Indirect Costs
            rows.append(_sec_hdr("H. INDIRECT COSTS"))
            sec_h = period.get("section_h", {})
            for ic in sec_h.get("indirect_costs", []):
                notes_parts = []
                if ic.get("rate"):
                    notes_parts.append(f'Rate: {ic["rate"]}%')
                if ic.get("base"):
                    notes_parts.append(f'Base: {_fmt(ic["base"])}')
                rows.append(_data_row(
                    ic.get("cost_type", ""),
                    role=" · ".join(notes_parts),
                    funds=_fmt(ic.get("fund_requested", "")),
                ))
            if sec_h.get("cognizant_agency"):
                rows.append(_data_row(
                    f'Cognizant Federal Agency: {sec_h["cognizant_agency"]}',
                ))
            rows.append(_total_row("Section H Total", _fmt(sec_h.get("total", ""))))

            # Section I — Total Direct + Indirect
            rows.append(_subtotal_row(
                "I. TOTAL DIRECT AND INDIRECT COSTS (G + H)",
                _fmt(period.get("total_costs", "")),
            ))

            # Fee line (Section J) — only shown when it differs from total_costs
            fee_total = period.get("total_costs_fee", "")
            if fee_total and fee_total != period.get("total_costs", ""):
                rows.append(
                    f'<tr class="bgt-grand-total-row">'
                    f'<td colspan="8" class="bgt-total-label">TOTAL COSTS + FEE</td>'
                    f'<td class="bgt-amt bgt-funds">{html.escape(_fmt(fee_total))}</td>'
                    f'</tr>'
                )

            period_html_list.append(
                f'<div class="budget-period-hdr">Period {P}: {start} – {end}</div>'
                f'<div class="bgt-table-wrap">'
                f'<table class="bgt-table">{_THEAD}'
                f'<tbody>{"".join(rows)}</tbody>'
                f'</table></div>'
            )

        just_line = (
            f'<div class="sub-info" style="font-size:.78rem;margin-bottom:.5rem">'
            f'{_icon("file", classes="icon-status")} Budget Justification: {html.escape(just_name)}</div>'
        ) if just_name else ""

        parts.append(
            f'<div class="card" style="margin-bottom:.7rem;border-left:4px solid var(--purple)">'
            f'<div class="budget-org">{org_name}</div>'
            f'<div class="sub-dim" style="font-size:.77rem">'
            f'{btype}{(" &nbsp;|&nbsp; UEI: " + uei) if uei else ""}</div>'
            f'{just_line}'
            f'{"".join(period_html_list)}'
            f'</div>'
        )
    return "\n".join(parts)


def _performance_site_manifest_html(manifest: list[dict]) -> str:
    if not manifest:
        return '<p style="color:#aaa;font-size:.88rem">No performance site manifest — run normalize-performance-site first.</p>'

    def _yn(v: bool) -> str:
        return "Yes" if v else "No"

    def _site_card(title: str, site: dict) -> str:
        location = ", ".join(
            x for x in [
                site.get("street1", ""),
                site.get("city", ""),
                site.get("state", "") or site.get("province", ""),
                site.get("country", ""),
                site.get("zip_postal_code", ""),
            ] if x
        ) or "—"
        org = site.get("organization_name", "") or "—"
        uei = site.get("uei", "") or "—"
        district = site.get("congressional_district", "") or "—"
        return (
            f'<div class="card" style="margin:.5rem 0;padding:.8rem 1rem;border-left:4px solid var(--purple-lt)">'
            f'<div class="budget-org">{html.escape(title)}</div>'
            f'<div class="sub-info">Individual: {html.escape(_yn(bool(site.get("individual"))))}</div>'
            f'<div class="sub-info">Organization: {html.escape(org)}</div>'
            f'<div class="sub-info">UEI: {html.escape(uei)}</div>'
            f'<div class="sub-info">Location: {html.escape(location)}</div>'
            f'<div class="sub-info">Congressional District: {html.escape(district)}</div>'
            f'</div>'
        )

    parts = []
    for entry in manifest:
        source = html.escape(entry.get("source_pdf", "?"))
        attach = entry.get("additional_sites_attachment", {}) or {}
        attach_name = Path(attach.get("path") or "").name if attach.get("path") else ""
        body = [_site_card("Primary Site", entry.get("primary_site", {}))]
        for idx, site in enumerate(entry.get("other_sites", []), 1):
            body.append(_site_card(f"Other Site {idx}", site))
        if attach_name:
            body.append(f'<div class="sub-info" style="margin-top:.4rem">{_icon("file", classes="icon-status")} Additional Site Attachment: {html.escape(attach_name)}</div>')
        parts.append(
            f'<div class="card" style="margin-bottom:.7rem;border-left:4px solid var(--purple)">'
            f'<div class="budget-org">{source}</div>'
            f'{"".join(body)}'
            f'</div>'
        )
    return "\n".join(parts)


def _chrome_section() -> tuple[str, str]:
    """Return (chrome_btn_html, chrome_status_html)."""
    chrome_bin  = _find_chrome()
    chrome_info = _chrome_debug_status()
    if chrome_info["open"]:
        ver  = chrome_info["version"]
        tabs = chrome_info["tabs"]
        btn    = (f'<button class="btn-success btn-panel" style="cursor:default" disabled>'
                  f'{_icon("check", classes="icon-btn")}Chrome Ready</button>')
        status = f'{html.escape(ver)} — ready for automate'
        if tabs:
            status += f' · {tabs} tab(s)'
    elif chrome_bin:
        btn = (
            '<form method="POST" action="/launch-chrome" style="margin:0">'
            f'<button type="submit" class="btn-primary btn-panel">{_icon("globe", classes="icon-btn")}Launch Chrome</button>'
            '</form>'
        )
        status = (
            "Opens a debug Chrome window at grants.gov. "
            "<strong>Log in</strong>, navigate to the desired form, then click Automate below."
        )
    else:
        btn    = '<button class="btn-disabled btn-panel" disabled>Chrome not found</button>'
        status = "Install google-chrome or chromium-browser"
    return btn, status


def _render_page(tab: str = "keyperson") -> str:
    # ── shared data ──────────────────────────────────────────────────────────
    chrome_btn, chrome_status = _chrome_section()
    chrome_info = _chrome_debug_status()

    # ── Key Person tab data ──────────────────────────────────────────────────
    records     = _read_log()
    extract_map = _latest_extract_per_pdf(records)
    manifest    = _read_manifest()
    pdfs        = _input_pdfs()
    steps       = _pipeline_steps(pdfs, extract_map, manifest)
    agency      = _read_ui_settings().get("agency", "NIH_PHS")
    steps_html  = _steps_html(steps, agency)

    manifest_ready = bool(manifest) and chrome_info["open"]
    if manifest_ready:
        automate_btn = (
            '<form method="POST" action="/run-step" style="margin:0">'
            '<input type="hidden" name="step" value="automate">'
            f'<button type="submit" class="btn-automate btn-panel">{_icon("automate", classes="icon-btn")}Automate</button>'
            '</form>'
        )
    else:
        reasons = (["normalize first"] if not manifest else []) + (["launch Chrome"] if not chrome_info["open"] else [])
        automate_btn = (
            f'<button class="btn-disabled btn-panel" disabled title="Need to: {", ".join(reasons)}">'
            f'{_icon("automate", classes="icon-btn")}Automate</button>'
        )

    pdf_count  = len(pdfs)
    m_included = len([e for e in manifest if not e.get("exclude", False)])
    m_total    = len(manifest)
    warn_count = sum(
        len([w for w in e.get("validation", {}).get("warnings", [])
             if agency == "NIH_PHS" or ("NIH" not in w and "eRA" not in w)])
        for e in manifest
    )
    manifest_badge = "ok" if m_total and not warn_count else ("warn" if warn_count else "pend")
    warn_badge = (
        f'&nbsp;<span class="badge warn">{_icon("warning", classes="icon-status")}{warn_count} warning{"s" if warn_count != 1 else ""}</span>'
        if warn_count else ""
    )

    kp_content = _KP_TAB_CONTENT.format(
        automation_icon=_icon("pipelinechip", classes="icon-chip"),
        steps_html=steps_html,
        automate_btn=automate_btn,
        chrome_btn=chrome_btn,
        chrome_status=chrome_status,
        trash_icon=_icon("trash", classes="icon-btn"),
        folder_icon=_icon("pdfschip", classes="icon-chip"),
        upload_icon=_icon("upload"),
        manifest_icon=_icon("manifestchip", classes="icon-chip"),
        pdf_badge="ok" if pdf_count else "pend",
        pdf_count=pdf_count,
        pdf_plural="" if pdf_count == 1 else "s",
        pdf_table=_pdf_table(pdfs, extract_map),
        manifest_badge=manifest_badge,
        manifest_count=m_included,
        manifest_plural="" if m_included == 1 else "s",
        warn_badge=warn_badge,
        manifest_table=_manifest_table(manifest, agency),
    )

    # ── Budget tab data ──────────────────────────────────────────────────────
    budget_records     = _read_budget_log()
    budget_extract_map = _latest_budget_extract_per_pdf(budget_records)
    budget_manifest    = _read_budget_manifest()
    budget_pdfs        = _budget_input_pdfs()
    budget_steps       = _budget_pipeline_steps(budget_pdfs, budget_extract_map, budget_manifest)
    budget_steps_html  = _steps_html(budget_steps, "default")

    budget_manifest_ready = bool(budget_manifest) and chrome_info["open"]
    if budget_manifest_ready:
        budget_automate_btn = (
            '<form method="POST" action="/run-step" style="margin:0">'
            '<input type="hidden" name="step" value="automate-budget">'
            f'<button type="submit" class="btn-automate btn-panel">{_icon("automate", classes="icon-btn")}Automate</button>'
            '</form>'
        )
    else:
        b_reasons = (["normalize-budget first"] if not budget_manifest else []) + \
                    (["launch Chrome"] if not chrome_info["open"] else [])
        budget_automate_btn = (
            f'<button class="btn-disabled btn-panel" disabled title="Need to: {", ".join(b_reasons)}">'
            f'{_icon("automate", classes="icon-btn")}Automate</button>'
        )

    budget_pdf_count = len(budget_pdfs)
    bm_count         = len(budget_manifest)

    budget_content = _BUDGET_TAB_CONTENT.format(
        automation_icon=_icon("pipelinechip", classes="icon-chip"),
        budget_steps_html=budget_steps_html,
        budget_automate_btn=budget_automate_btn,
        chrome_btn=chrome_btn,
        chrome_status=chrome_status,
        trash_icon=_icon("trash", classes="icon-btn"),
        folder_icon=_icon("pdfschip", classes="icon-chip"),
        upload_icon=_icon("upload"),
        budget_icon=_icon("manifestchip", classes="icon-chip"),
        budget_pdf_badge="ok" if budget_pdf_count else "pend",
        budget_pdf_count=budget_pdf_count,
        budget_pdf_plural="" if budget_pdf_count == 1 else "s",
        budget_pdf_table=_budget_pdf_table(budget_pdfs, budget_extract_map),
        budget_manifest_badge="ok" if bm_count else "pend",
        budget_manifest_count=bm_count,
        budget_manifest_plural="" if bm_count == 1 else "s",
        budget_manifest_html=_budget_manifest_html(budget_manifest),
    )

    # ── Performance Site tab data ────────────────────────────────────────────
    ps_records = _read_performance_site_log()
    ps_extract_map = _latest_performance_site_extract_per_pdf(ps_records)
    ps_manifest = _read_performance_site_manifest()
    ps_pdfs = _performance_site_input_pdfs()
    ps_steps = _performance_site_pipeline_steps(ps_pdfs, ps_extract_map, ps_manifest)
    ps_steps_html = _steps_html(ps_steps, "default")

    ps_manifest_ready = bool(ps_manifest) and chrome_info["open"]
    if ps_manifest_ready:
        ps_automate_btn = (
            '<form method="POST" action="/run-step" style="margin:0">'
            '<input type="hidden" name="step" value="automate-performance-site">'
            f'<button type="submit" class="btn-automate btn-panel">{_icon("automate", classes="icon-btn")}Automate</button>'
            '</form>'
        )
    else:
        ps_reasons = (["normalize-performance-site first"] if not ps_manifest else []) + \
                     (["launch Chrome"] if not chrome_info["open"] else [])
        ps_automate_btn = (
            f'<button class="btn-disabled btn-panel" disabled title="Need to: {", ".join(ps_reasons)}">'
            f'{_icon("automate", classes="icon-btn")}Automate</button>'
        )

    ps_pdf_count = len(ps_pdfs)
    ps_manifest_count = len(ps_manifest)
    ps_content = _PERFORMANCE_SITE_TAB_CONTENT.format(
        automation_icon=_icon("pipelinechip", classes="icon-chip"),
        ps_steps_html=ps_steps_html,
        ps_automate_btn=ps_automate_btn,
        chrome_btn=chrome_btn,
        chrome_status=chrome_status,
        trash_icon=_icon("trash", classes="icon-btn"),
        folder_icon=_icon("pdfschip", classes="icon-chip"),
        upload_icon=_icon("upload"),
        pin_icon=_icon("manifestchip", classes="icon-chip"),
        ps_pdf_badge="ok" if ps_pdf_count else "pend",
        ps_pdf_count=ps_pdf_count,
        ps_pdf_plural="" if ps_pdf_count == 1 else "s",
        ps_pdf_table=_performance_site_pdf_table(ps_pdfs, ps_extract_map),
        ps_manifest_badge="ok" if ps_manifest_count else "pend",
        ps_manifest_count=ps_manifest_count,
        ps_manifest_plural="" if ps_manifest_count == 1 else "s",
        ps_manifest_html=_performance_site_manifest_html(ps_manifest),
    )

    # ── Assemble page ─────────────────────────────────────────────────────────
    if tab == "budget":
        tab_content      = budget_content
        kp_tab_active    = ""
        budget_tab_active = "active"
        ps_tab_active = ""
        tab_title        = "RRTard — Budget"
        header_reset_btn = (
            '<form method="POST" action="/reset-budget-extracted" style="margin:0" '
            'onsubmit="return confirm(\'Clear all extracted budget XML, attachments and manifest? Input PDFs are kept.\')">'
            f'<button type="submit" class="btn-warn header-utility-btn">{_icon("trash", classes="icon-btn")}Reset</button>'
            '</form>'
        )
    elif tab == "performance-site":
        tab_content      = ps_content
        kp_tab_active    = ""
        budget_tab_active = ""
        ps_tab_active = "active"
        tab_title        = "RRTard — Performance Site"
        header_reset_btn = (
            '<form method="POST" action="/reset-performance-site-extracted" style="margin:0" '
            'onsubmit="return confirm(\'Clear all extracted Performance Site XML, attachments and manifest? Input PDFs are kept.\')">'
            f'<button type="submit" class="btn-warn header-utility-btn">{_icon("trash", classes="icon-btn")}Reset</button>'
            '</form>'
        )
    else:
        tab_content      = kp_content
        kp_tab_active    = "active"
        budget_tab_active = ""
        ps_tab_active = ""
        tab_title        = "RRTard — Key Person"
        header_reset_btn = (
            '<form method="POST" action="/reset-extracted" style="margin:0" '
            'onsubmit="return confirm(\'Clear all extracted XML, attachments and manifest? Input PDFs are kept.\')">'
            f'<button type="submit" class="btn-warn header-utility-btn">{_icon("trash", classes="icon-btn")}Reset</button>'
            '</form>'
        )

    return _PAGE.format(
        css=(
            _CSS
            .replace("__RASTERFORGE_FONT__", _font_data_uri("RasterForgeRegular-JpBgm.ttf"))
            .replace("__PIXELOID_FONT__", _font_data_uri("PixeloidSans-lxa3y.ttf"))
            .replace("__NINETEEN_FONT__", _font_data_uri("NineteenNinetySeven-11XB.ttf"))
            .replace("__DOSREADABLE_FONT__", _font_data_uri("Px437_DOS-V_re_ANK30.ttf"))
        ),
        js=(
            _JS
            .replace("__CLOCK_ICON__", _icon("warning"))
            .replace("__PLAY_ICON__", _icon("play", classes="icon-btn"))
            .replace("__PAUSE_ICON__", _icon("pause", classes="icon-btn"))
        ),
        pause_icon=_icon("pause", classes="icon-btn"),
        people_icon=_icon("people", classes="icon-btn"),
        budget_icon=_icon("budget", classes="icon-btn"),
        pin_icon=_icon("pin", classes="icon-btn"),
        header_reset_btn=header_reset_btn,
        tab_title=tab_title,
        kp_tab_active=kp_tab_active,
        budget_tab_active=budget_tab_active,
        ps_tab_active=ps_tab_active,
        tab_content=tab_content,
    )


# ── HTTP handler ──────────────────────────────────────────────────────────────

_ALLOWED_STEPS = {
    "fetch-schemas", "extract", "validate", "normalize", "automate",
    "extract-budget", "normalize-budget", "automate-budget",
    "extract-performance-site", "normalize-performance-site", "automate-performance-site",
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_html(self, body: str, code: int = 200) -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data: bytes, content_type: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload, code: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str = "/") -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            params = parse_qs(parsed.query)
            tab = params.get("tab", ["keyperson"])[0]
            self._send_html(_render_page(tab))
        elif parsed.path == "/contact-directory":
            self._send_json(_contact_directory_payload())
        elif parsed.path.startswith("/img/"):
            target = (BASE / parsed.path.lstrip("/")).resolve()
            img_root = (BASE / "img").resolve()
            if img_root in target.parents and target.is_file():
                suffix = target.suffix.lower()
                if suffix == ".svg":
                    content_type = "image/svg+xml"
                elif suffix == ".gif":
                    content_type = "image/gif"
                elif suffix == ".png":
                    content_type = "image/png"
                else:
                    content_type = "application/octet-stream"
                self._send_bytes(target.read_bytes(), content_type)
            else:
                self._send_html("<h1>404</h1>", 404)
        else:
            self._send_html("<h1>404</h1>", 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        if path == "/upload-pdf":
            ct = self.headers.get("Content-Type", "")
            INPUT_DIR.mkdir(exist_ok=True)
            for fname, data in _parse_multipart_pdfs(ct, body):
                safe = Path(fname).name
                if safe and safe.lower().endswith(".pdf"):
                    (INPUT_DIR / safe).write_bytes(data)
            self._redirect()

        elif path == "/remove-pdf":
            params = parse_qs(body.decode(errors="replace"))
            fname = params.get("filename", [""])[0]
            safe = Path(fname).name
            if safe and safe.lower().endswith(".pdf"):
                target = INPUT_DIR / safe
                if target.exists():
                    target.unlink()
            self._redirect()

        elif path == "/upload-budget-pdf":
            ct = self.headers.get("Content-Type", "")
            BUDGET_INPUT_DIR.mkdir(exist_ok=True)
            for fname, data in _parse_multipart_pdfs(ct, body):
                safe = Path(fname).name
                if safe and safe.lower().endswith(".pdf"):
                    (BUDGET_INPUT_DIR / safe).write_bytes(data)
            self._redirect("/?tab=budget")

        elif path == "/upload-performance-site-pdf":
            ct = self.headers.get("Content-Type", "")
            PS_INPUT_DIR.mkdir(exist_ok=True)
            for fname, data in _parse_multipart_pdfs(ct, body):
                safe = Path(fname).name
                if safe and safe.lower().endswith(".pdf"):
                    (PS_INPUT_DIR / safe).write_bytes(data)
            self._redirect("/?tab=performance-site")

        elif path == "/remove-budget-pdf":
            params = parse_qs(body.decode(errors="replace"))
            fname = params.get("filename", [""])[0]
            safe = Path(fname).name
            if safe and safe.lower().endswith(".pdf"):
                target = BUDGET_INPUT_DIR / safe
                if target.exists():
                    target.unlink()
            self._redirect("/?tab=budget")

        elif path == "/remove-performance-site-pdf":
            params = parse_qs(body.decode(errors="replace"))
            fname = params.get("filename", [""])[0]
            safe = Path(fname).name
            if safe and safe.lower().endswith(".pdf"):
                target = PS_INPUT_DIR / safe
                if target.exists():
                    target.unlink()
            self._redirect("/?tab=performance-site")

        elif path == "/run-step":
            params = parse_qs(body.decode(errors="replace"))
            step = params.get("step", [""])[0]
            if step == "normalize":
                agency = _read_ui_settings().get("agency", "NIH_PHS")
                _spawn_step("normalize", ["--agency", agency])
            elif step in _ALLOWED_STEPS:
                _spawn_step(step, [])
            # Redirect back to appropriate tab
            budget_steps = {"extract-budget", "normalize-budget", "automate-budget"}
            ps_steps = {"extract-performance-site", "normalize-performance-site", "automate-performance-site"}
            redirect_tab = "budget" if step in budget_steps else ("performance-site" if step in ps_steps else "keyperson")
            self._redirect(f"/?tab={redirect_tab}")

        elif path == "/set-agency":
            params = parse_qs(body.decode(errors="replace"))
            agency = params.get("agency", ["NIH_PHS"])[0]
            if agency in {v for v, _ in _AGENCIES}:
                s = _read_ui_settings()
                s["agency"] = agency
                _write_ui_settings(s)
            self._redirect()

        elif path == "/save-manifest":
            params = parse_qs(body.decode(errors="replace"), keep_blank_values=True)
            manifest = _read_manifest()
            for i, entry in enumerate(manifest):
                p = entry["person"]
                include_vals = params.get(f"include_{i}", ["0"])
                entry["exclude"] = "1" not in include_vals
                if f"role_{i}" in params:
                    p["project_role"] = params[f"role_{i}"][0].strip()
                if f"other_role_{i}" in params:
                    p["other_project_role_category"] = params[f"other_role_{i}"][0].strip()
                if f"org_{i}" in params:
                    p["organization_name"] = params[f"org_{i}"][0].strip()
                if f"credential_{i}" in params:
                    p["credential"] = params[f"credential_{i}"][0].strip()
                if f"email_{i}" in params:
                    p["email"] = params[f"email_{i}"][0].strip()

            add_contacts = params.get("add_contacts", [""])[0].strip()
            if add_contacts:
                try:
                    requested_emails = json.loads(add_contacts)
                except json.JSONDecodeError:
                    requested_emails = []
                if not isinstance(requested_emails, list):
                    requested_emails = []

                contacts_by_email = _read_contacts_directory()
                existing_emails = {
                    _clean_ws(str((entry.get("person") or {}).get("email") or "")).lower()
                    for entry in manifest
                    if _clean_ws(str((entry.get("person") or {}).get("email") or ""))
                }
                for raw_email in requested_emails:
                    email_key = _clean_ws(str(raw_email or "")).lower()
                    if not email_key or email_key in existing_emails:
                        continue
                    contact = contacts_by_email.get(email_key)
                    if not contact:
                        continue
                    manifest.append(_manifest_entry_from_contact(contact))
                    existing_emails.add(email_key)
            REVIEW_DIR.mkdir(exist_ok=True)
            (REVIEW_DIR / "import_manifest.json").write_text(json.dumps(manifest, indent=2))
            self._redirect()

        elif path == "/launch-chrome":
            chrome_bin = _find_chrome()
            if chrome_bin and not _chrome_debug_status()["open"]:
                debug_profile = BASE / ".chrome-debug-profile"
                debug_profile.mkdir(exist_ok=True)
                subprocess.Popen(
                    [chrome_bin,
                     "--remote-debugging-port=9222",
                     f"--user-data-dir={debug_profile}",
                     "--no-first-run",
                     "--no-default-browser-check",
                     "https://apply07.grants.gov/"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            self._redirect()

        elif path == "/reset-extracted":
            for d in (XML_DIR, ATT_DIR):
                if d.exists():
                    shutil.rmtree(d)
            for fname in ("import_manifest.json", "import_manifest.xlsx",
                          "validation_report.html"):
                f = REVIEW_DIR / fname
                if f.exists():
                    f.unlink()
            self._redirect()

        elif path == "/reset-budget-extracted":
            for d in (BUDGET_XML_DIR, BUDGET_ATT_DIR):
                if d.exists():
                    shutil.rmtree(d)
            for fname in ("budget_manifest.json", "budget_manifest.xlsx"):
                f = REVIEW_DIR / fname
                if f.exists():
                    f.unlink()
            self._redirect("/?tab=budget")

        elif path == "/reset-performance-site-extracted":
            for d in (PS_XML_DIR, PS_ATT_DIR):
                if d.exists():
                    shutil.rmtree(d)
            for fname in ("performance_site_manifest.json", "performance_site_manifest.xlsx"):
                f = REVIEW_DIR / fname
                if f.exists():
                    f.unlink()
            self._redirect("/?tab=performance-site")

        else:
            self._send_html("<h1>404</h1>", 404)


def run(port: int = 8080) -> None:
    server = HTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://localhost:{port}"
    print(f"Dashboard → {url}  (Ctrl-C to stop)")
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run(port)
