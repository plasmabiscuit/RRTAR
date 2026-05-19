from __future__ import annotations

"""
Validate extracted RR_KeyPersonExpanded XML files against local XSD schemas and
business rules. Generates review/validation_report.html.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from lxml import etree

BASE = Path(__file__).resolve().parents[1]
XML_DIR = BASE / "extracted-xml"
SCHEMA_DIR = BASE / "schemas"
REVIEW_DIR = BASE / "review"
VERSION_FILE = BASE / "config" / "form_version.json"

FORM_NS = "http://apply.grants.gov/forms/RR_KeyPersonExpanded_4_0-V4.0"
ATT_NS = "http://apply.grants.gov/system/Attachments-V1.0"
GLOB_LIB_NS = "http://apply.grants.gov/system/GlobalLibrary-V2.0"

REQUIRED_PROFILE_FIELDS = [
    "FirstName", "LastName", "OrganizationName",
    "Street1", "City", "Country", "Phone", "Email", "ProjectRole",
]


@dataclass
class PersonResult:
    source_element: str  # "PDPI" or "KeyPerson[N]"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class FileResult:
    xml_path: str
    schema_valid: bool = False
    schema_errors: list[str] = field(default_factory=list)
    form_version: str = ""
    persons: list[PersonResult] = field(default_factory=list)
    file_errors: list[str] = field(default_factory=list)


def _build_schema() -> etree.XMLSchema:
    """Build an XMLSchema using local schema files, resolving imports locally."""
    primary_xsd = SCHEMA_DIR / "RR_KeyPersonExpanded_4_0-V4.0.xsd"
    if not primary_xsd.exists():
        raise FileNotFoundError(f"Primary XSD not found: {primary_xsd}")

    # Parse the primary XSD and patch schemaLocation attributes to local paths.
    xsd_tree = etree.parse(str(primary_xsd))
    ns = {"xs": "http://www.w3.org/2001/XMLSchema"}
    schema_map = {
        "http://apply.grants.gov/system/Attachments-V1.0":   "Attachments-V1.0.xsd",
        "http://apply.grants.gov/system/Global-V1.0":        "Global-V1.0.xsd",
        "http://apply.grants.gov/system/GlobalLibrary-V2.0": "GlobalLibrary-V2.0.xsd",
        "http://apply.grants.gov/system/UniversalCodes-V2.0":"UniversalCodes-V2.0.xsd",
    }
    for imp in xsd_tree.findall("xs:import", ns):
        ns_uri = imp.get("namespace", "")
        if ns_uri in schema_map:
            local = SCHEMA_DIR / schema_map[ns_uri]
            if local.exists():
                imp.set("schemaLocation", local.as_uri())

    return etree.XMLSchema(xsd_tree)


def _get_text(el: etree._Element, *path_parts: str, ns: str = FORM_NS) -> str:
    """Walk nested elements and return text or empty string."""
    cur = el
    for part in path_parts:
        nxt = cur.find(f"{{{ns}}}{part}")
        if nxt is None:
            return ""
        cur = nxt
    return (cur.text or "").strip()


def _get_glob_text(el: etree._Element, *path_parts: str) -> str:
    return _get_text(el, *path_parts, ns=GLOB_LIB_NS)


def _form_ns(el: Optional[etree._Element]) -> str:
    return etree.QName(el.tag).namespace if el is not None else FORM_NS


def _validate_person(person_el: etree._Element, label: str, agency: str = "default") -> PersonResult:
    result = PersonResult(source_element=label)
    form_ns = _form_ns(person_el)
    profile = person_el.find(f"{{{form_ns}}}Profile")
    if profile is None:
        result.errors.append("Missing <Profile> element")
        return result

    name_el = profile.find(f"{{{form_ns}}}Name")
    addr_el = profile.find(f"{{{form_ns}}}Address")

    def text(el, tag, ns=FORM_NS):
        if el is None:
            return ""
        effective_ns = form_ns if ns == FORM_NS else ns
        child = el.find(f"{{{effective_ns}}}{tag}")
        return (child.text or "").strip() if child is not None else ""

    # Name and Address children use GLOB_LIB_NS; other profile fields use FORM_NS
    first  = text(name_el, "FirstName", GLOB_LIB_NS) if name_el is not None else ""
    last   = text(name_el, "LastName",  GLOB_LIB_NS) if name_el is not None else ""
    org    = text(profile, "OrganizationName", FORM_NS)
    phone  = text(profile, "Phone",            FORM_NS)
    email  = text(profile, "Email",            FORM_NS)
    role   = text(profile, "ProjectRole",      FORM_NS)

    street1 = text(addr_el, "Street1",       GLOB_LIB_NS) if addr_el is not None else ""
    city    = text(addr_el, "City",           GLOB_LIB_NS) if addr_el is not None else ""
    country = text(addr_el, "Country",        GLOB_LIB_NS) if addr_el is not None else ""
    state   = text(addr_el, "State",          GLOB_LIB_NS) if addr_el is not None else ""
    zip_    = text(addr_el, "ZipPostalCode",  GLOB_LIB_NS) if addr_el is not None else ""

    missing = []
    for fname, val in [("FirstName", first), ("LastName", last), ("OrganizationName", org),
                       ("Street1", street1), ("City", city), ("Country", country),
                       ("Phone", phone), ("Email", email), ("ProjectRole", role)]:
        if not val:
            missing.append(fname)

    # State/ZIP conditionally required for US persons
    if country.upper() in ("USA", "USA: UNITED STATES", "UNITED STATES"):
        if not state:
            missing.append("State (required for US address)")
        if not zip_:
            missing.append("ZipPostalCode (required for US address)")

    if missing:
        result.errors.append(f"Missing required fields: {', '.join(missing)}")

    # Agency-specific warnings
    cred = text(profile, "Credential", FORM_NS)
    if not cred and agency == "NIH_PHS":
        result.warnings.append("Credential (eRA Commons username) is blank — required for NIH submissions")

    if role == "Co-PD/PI" and agency == "NIH_PHS":
        result.warnings.append(
            "Role is Co-PD/PI — NIH multiple-PI applications should use PD/PI for all PD/PIs"
        )

    # Biosketch check
    bio_el = profile.find(f"{{{form_ns}}}BioSketchsAttached")
    if bio_el is None or bio_el.find(f"{{{form_ns}}}BioSketchAttached") is None:
        result.errors.append("No BioSketchAttached element — biosketch is required")

    return result


def validate_file(xml_path: Path, schema: etree.XMLSchema, agency: str = "default") -> FileResult:
    result = FileResult(xml_path=str(xml_path.relative_to(BASE)))

    try:
        tree = etree.parse(str(xml_path))
    except etree.XMLSyntaxError as exc:
        result.file_errors.append(f"XML parse error: {exc}")
        return result

    root = tree.getroot()
    root_ns = _form_ns(root)
    # FormVersion is namespace-qualified in actual extracted XMLs
    version_attr = (root.get(f"{{{root_ns}}}FormVersion")
                    or root.get("FormVersion"))
    result.form_version = version_attr or "unknown"

    cfg = json.loads(VERSION_FILE.read_text())
    expected = cfg.get("expected_version", "4.0")
    if result.form_version != expected:
        result.file_errors.append(
            f"FormVersion '{result.form_version}' != expected '{expected}'. Cannot proceed."
        )
    elif root_ns == FORM_NS:
        result.schema_valid = schema.validate(tree)
        if not result.schema_valid:
            result.schema_errors = [str(e) for e in schema.error_log]
    else:
        result.schema_errors.append(
            f"Skipped 4.0 schema validation for namespace '{root_ns}'."
        )

    # Per-person business rules
    for child in root:
        local = etree.QName(child.tag).localname
        if local == "PDPI":
            result.persons.append(_validate_person(child, "PDPI", agency))
        elif local == "KeyPerson":
            idx = sum(1 for p in result.persons if p.source_element.startswith("KeyPerson"))
            result.persons.append(_validate_person(child, f"KeyPerson[{idx}]", agency))

    return result


def _html_row_class(r: FileResult) -> str:
    if r.file_errors:
        return "error"
    if any(p.errors for p in r.persons):
        return "warn"
    return "ok"


def generate_report(results: List[FileResult], slot_count: Optional[int] = None) -> Path:
    REVIEW_DIR.mkdir(exist_ok=True)
    total_persons = sum(len(r.persons) for r in results if not r.file_errors)

    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Key Person Import Validation Report</title>",
        "<style>",
        "body{font-family:sans-serif;margin:2rem}",
        "table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ccc;padding:.4rem .7rem;text-align:left}",
        "tr.ok td:first-child{background:#d4edda}",
        "tr.warn td:first-child{background:#fff3cd}",
        "tr.error td:first-child{background:#f8d7da}",
        ".tag-err{color:#721c24;font-weight:bold}",
        ".tag-warn{color:#856404}",
        "</style></head><body>",
        "<h1>RR Key Person Import — Validation Report</h1>",
        f"<p>Total XML files: {len(results)} &nbsp;|&nbsp; Total persons: {total_persons}</p>",
    ]

    if slot_count is not None and total_persons > slot_count:
        lines.append(
            f"<p class='tag-err'>&#9888; {total_persons} persons exceed available target slots "
            f"({slot_count}). Automation blocked until resolved.</p>"
        )

    lines += [
        "<table>",
        "<thead><tr><th>File</th><th>Version</th><th>Schema</th><th>Persons</th><th>Issues</th></tr></thead>",
        "<tbody>",
    ]

    for r in results:
        cls = _html_row_class(r)
        issues = []
        issues += [f"<span class='tag-err'>FILE: {e}</span>" for e in r.file_errors]
        issues += [f"<span class='tag-err'>SCHEMA: {e}</span>" for e in r.schema_errors[:3]]
        for p in r.persons:
            for e in p.errors:
                issues.append(f"<span class='tag-err'>{p.source_element}: {e}</span>")
            for w in p.warnings:
                issues.append(f"<span class='tag-warn'>{p.source_element}: &#9888; {w}</span>")

        lines.append(
            f"<tr class='{cls}'>"
            f"<td>{r.xml_path}</td>"
            f"<td>{r.form_version}</td>"
            f"<td>{'&#10003;' if r.schema_valid else '&#10007;'}</td>"
            f"<td>{len(r.persons)}</td>"
            f"<td>{'<br>'.join(issues) or '—'}</td>"
            f"</tr>"
        )

    lines += ["</tbody></table></body></html>"]
    out = REVIEW_DIR / "validation_report.html"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _read_agency() -> str:
    settings_path = BASE / "config" / "ui_settings.json"
    try:
        return json.loads(settings_path.read_text()).get("agency", "default")
    except Exception:
        return "default"


def run(available_slots: Optional[int] = None) -> List[FileResult]:
    xmls = sorted(XML_DIR.glob("*.xml"))
    if not xmls:
        print(f"No XML files found in {XML_DIR}")
        return []

    agency = _read_agency()
    print(f"  agency: {agency}")

    missing_schemas = [
        f for f in ["Attachments-V1.0.xsd", "Global-V1.0.xsd",
                    "GlobalLibrary-V2.0.xsd", "UniversalCodes-V2.0.xsd"]
        if not (SCHEMA_DIR / f).exists()
    ]
    if missing_schemas:
        print(f"WARNING: Dependency schemas missing ({missing_schemas}). "
              "Run fetch-schemas first. Schema validation may fail.")

    try:
        schema = _build_schema()
    except Exception as exc:
        print(f"Could not build XMLSchema: {exc}. Schema validation disabled.")
        schema = None

    results = []
    hard_stop = False

    for xml_path in xmls:
        print(f"  validating {xml_path.name} …", end="", flush=True)
        if schema:
            r = validate_file(xml_path, schema, agency)
        else:
            r = FileResult(xml_path=str(xml_path.relative_to(BASE)))
            r.file_errors.append("Schema not available; structural validation skipped")
        results.append(r)

        has_errors = bool(r.file_errors or any(p.errors for p in r.persons))
        has_version_stop = any("FormVersion" in e for e in r.file_errors)
        status = "STOP" if has_version_stop else ("ERRORS" if has_errors else "ok")
        warn_count = sum(len(p.warnings) for p in r.persons)
        print(f" {status}  persons={len(r.persons)} warnings={warn_count}")

        if has_version_stop:
            hard_stop = True

    total_persons = sum(len(r.persons) for r in results if not r.file_errors)
    if available_slots is not None and total_persons > available_slots:
        print(f"\nHARD STOP: {total_persons} persons exceed {available_slots} available slots.")
        hard_stop = True

    report_path = generate_report(results, available_slots)
    print(f"\nReport: {report_path.relative_to(BASE)}")

    if hard_stop:
        print("One or more hard-stop conditions found. Resolve before proceeding to normalize/automate.")
        sys.exit(1)

    return results


if __name__ == "__main__":
    slots = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(slots)
