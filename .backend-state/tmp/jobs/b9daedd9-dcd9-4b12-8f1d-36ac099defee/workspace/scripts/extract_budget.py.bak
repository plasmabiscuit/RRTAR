"""
Extract XFA datasets XML and embedded attachments from R&R Budget PDFs.

Outputs:
  extracted-budget-xml/{stem}.xml         — clean RR_Budget_3_0 element
  extracted-budget-attachments/{desc}.pdf — budget justification PDFs
  audit/run_log.jsonl                     — one JSON line per PDF processed
"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
XML_DIR  = BASE / "extracted-budget-xml"
ATT_DIR  = BASE / "extracted-budget-attachments"
AUDIT_DIR = BASE / "audit"
LOG_FILE  = AUDIT_DIR / "run_log.jsonl"
_VENV_PYTHON = BASE / ".venv" / "bin" / "python3"


def _ensure_modules(modules: list[str]) -> None:
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    if not missing:
        return
    if _VENV_PYTHON.exists() and sys.executable != str(_VENV_PYTHON):
        os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), __file__, *sys.argv[1:]])
    missing_csv = ", ".join(missing)
    raise ImportError(f"Missing required module(s): {missing_csv}")


_ensure_modules(["lxml", "pikepdf", "pdfplumber"])

import pikepdf
import pdfplumber
from lxml import etree

XFA_NS   = "http://www.xfa.org/schema/xfa-data/1.0/"
FORM_NS  = "http://apply.grants.gov/forms/RR_Budget_3_0-V3.0"
FORM_LOCAL = "RR_Budget_3_0"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def safe_filename(s: str) -> str:
    return re.sub(r"[^\w.\-]", "_", s)


def _is_streamlyne_budget_pdf(pdf_path: Path) -> bool:
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            if not pdf.pages:
                return False
            text = pdf.pages[0].extract_text(x_tolerance=1.5, y_tolerance=3) or ""
    except Exception:
        return False
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    return first_line.startswith("Streamlyne -") or first_line.startswith("Streamlyne-")


def _is_printed_rr_budget_pdf(pdf_path: Path) -> bool:
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            if not pdf.pages:
                return False
            text = pdf.pages[0].extract_text(x_tolerance=1.5, y_tolerance=3) or ""
    except Exception:
        return False
    return "RESEARCH & RELATED BUDGET - Budget Period" in text


def _load_streamlyne_metadata(pdf_path: Path) -> dict:
    meta_path = pdf_path.with_suffix(".budget.json")
    if not meta_path.exists():
        return {}
    data = json.loads(meta_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Metadata file must contain a JSON object: {meta_path}")
    data["_meta_path"] = str(meta_path)
    return data


def _copy_budget_justification(source: Path, stem: str) -> tuple[Path, dict]:
    if not source.exists():
        raise FileNotFoundError(f"Budget justification not found: {source}")
    ATT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or ".pdf"
    dest = ATT_DIR / f"{stem}_BudgetJustification{suffix}"
    if dest.exists() and dest.resolve() != source.resolve():
        for n in range(2, 100):
            alt = ATT_DIR / f"{stem}_BudgetJustification_{n}{suffix}"
            if not alt.exists():
                dest = alt
                break
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    return dest, {
        "key": "budget_justification",
        "desc": "Budget Justification",
        "path": str(dest.relative_to(BASE)),
    }


def _get_xfa_array(pdf: pikepdf.Pdf) -> list[tuple[str, bytes]]:
    xfa = pdf.Root.AcroForm.XFA
    if isinstance(xfa, pikepdf.Stream):
        return [("single", bytes(xfa.read_bytes()))]
    items = list(xfa)
    if len(items) % 2 != 0:
        print(f"  WARNING: XFA array has odd length ({len(items)}); last item dropped", flush=True)
    return [
        (str(items[i]), bytes(items[i + 1].read_bytes()))
        for i in range(0, len(items) - 1, 2)
    ]


def _find_datasets(packets: list[tuple[str, bytes]]) -> bytes:
    for name, data in packets:
        if name == "datasets":
            return data
    for _name, data in packets:
        if b"xfa:datasets" in data or b"<datasets" in data:
            return data
    raise ValueError("Could not locate XFA datasets packet")


def _extract_form_element(datasets_bytes: bytes) -> etree._Element:
    root = etree.fromstring(datasets_bytes)
    matches = root.findall(f".//{{{FORM_NS}}}{FORM_LOCAL}")
    if matches:
        return matches[0]
    matches2 = root.xpath(f"//*[local-name()='{FORM_LOCAL}']")
    if matches2:
        return matches2[0]
    raise ValueError(f"Element '{FORM_LOCAL}' not found in datasets packet")


def _extract_embedded_files(pdf: pikepdf.Pdf, att_dir: Path, stem: str) -> list[dict]:
    results = []
    try:
        names_tree = pdf.Root.Names.EmbeddedFiles.Names
    except AttributeError:
        return results

    items = list(names_tree)
    for i in range(0, len(items), 2):
        key = str(items[i])
        file_spec = items[i + 1]

        desc = key
        try:
            desc = str(file_spec.Desc)
        except AttributeError:
            pass

        try:
            ef_stream = file_spec.EF.F
            data = bytes(ef_stream.read_bytes())
        except AttributeError:
            results.append({"key": key, "desc": desc, "path": None, "error": "no EF/F stream"})
            continue

        fname = f"{stem}_BudgetJustification.pdf"
        dest = att_dir / fname
        # Resolve collision
        if dest.exists():
            for n in range(2, 100):
                alt = att_dir / f"{stem}_BudgetJustification_{n}.pdf"
                if not alt.exists():
                    dest = alt
                    break
        dest.write_bytes(data)
        results.append({"key": key, "desc": desc, "path": str(dest.relative_to(BASE))})

    return results


def _count_periods(form_el: etree._Element) -> int:
    return len(form_el.findall(f"{{{FORM_NS}}}BudgetYear"))


def _extract_streamlyne_pdf(pdf_path: Path) -> dict:
    import streamlyne_xml

    metadata = _load_streamlyne_metadata(pdf_path)
    key_person_roles = metadata.get("key_person_roles") or {}
    if not isinstance(key_person_roles, dict):
        raise ValueError("Streamlyne metadata key_person_roles must be an object mapping name to role")
    key_person_roles = {
        streamlyne_xml.normalize_person_name(str(name)): str(role).strip()
        for name, role in key_person_roles.items()
        if str(name).strip() and str(role).strip()
    }

    lines = streamlyne_xml.extract_lines(pdf_path)
    budget = streamlyne_xml.parse_budget_pdf(lines, set(key_person_roles))
    if not key_person_roles and budget.pi_name:
        key_person_roles[streamlyne_xml.normalize_person_name(budget.pi_name)] = "PD/PI"

    org_name = (
        str(metadata.get("organization_name") or "").strip()
        or (budget.lead_unit_name or "").strip()
        or pdf_path.stem
    )
    budget_type = str(metadata.get("budget_type") or "Project").strip() or "Project"
    uei = str(metadata.get("uei") or "").strip()

    justification_filename = None
    attachments: list[dict] = []
    just_value = str(metadata.get("budget_justification") or "").strip()
    if just_value:
        just_path = Path(just_value)
        if not just_path.is_absolute():
            just_path = (pdf_path.parent / just_path).resolve()
        copied_path, attachment_record = _copy_budget_justification(just_path, pdf_path.stem)
        justification_filename = copied_path.name
        attachments.append(attachment_record)

    tree = streamlyne_xml.create_rr_budget_xml(
        budget,
        uei=uei,
        organization_name=org_name,
        budget_type=budget_type,
        key_person_roles=key_person_roles,
        budget_justification_filename=justification_filename,
    )

    out_xml = XML_DIR / f"{pdf_path.stem}.xml"
    tree.write(
        str(out_xml),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
    )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "form_type": "budget",
        "extractor": "streamlyne",
        "source_pdf": str(pdf_path),
        "source_sha256": sha256_file(pdf_path),
        "organization": org_name,
        "period_count": 1,
        "extracted_xml": str(out_xml.relative_to(BASE)),
        "attachments": attachments,
        "metadata_file": metadata.get("_meta_path"),
    }


def _extract_printed_rr_budget_pdf(pdf_path: Path) -> dict:
    import printed_rr_budget

    lines = printed_rr_budget.extract_lines(pdf_path)
    budget = printed_rr_budget.parse_printed_rr_budget(lines)
    tree = printed_rr_budget.build_rr_budget_xml(budget)

    out_xml = XML_DIR / f"{pdf_path.stem}.xml"
    tree.write(
        str(out_xml),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
    )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "form_type": "budget",
        "extractor": "printed_rr_budget",
        "source_pdf": str(pdf_path),
        "source_sha256": sha256_file(pdf_path),
        "organization": budget.organization_name,
        "period_count": len(budget.periods),
        "extracted_xml": str(out_xml.relative_to(BASE)),
        "attachments": [],
    }


def extract_pdf(pdf_path: Path) -> dict:
    print(f"  {pdf_path.name} …", end="", flush=True)
    XML_DIR.mkdir(parents=True, exist_ok=True)
    ATT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    if _is_streamlyne_budget_pdf(pdf_path):
        record = _extract_streamlyne_pdf(pdf_path)
        print(
            f" ok  (streamlyne, org={record['organization']!r}, "
            f"periods={record['period_count']}, attachments={len(record['attachments'])})"
        )
        return record

    if _is_printed_rr_budget_pdf(pdf_path):
        record = _extract_printed_rr_budget_pdf(pdf_path)
        print(
            f" ok  (printed_rr_budget, org={record['organization']!r}, "
            f"periods={record['period_count']}, attachments={len(record['attachments'])})"
        )
        return record

    pdf = pikepdf.open(pdf_path)
    packets = _get_xfa_array(pdf)
    datasets_bytes = _find_datasets(packets)
    form_el = _extract_form_element(datasets_bytes)

    org_name = (form_el.findtext(f"{{{FORM_NS}}}OrganizationName") or "").strip()
    period_count = _count_periods(form_el)

    out_xml = XML_DIR / (pdf_path.stem + ".xml")
    out_xml.write_bytes(
        etree.tostring(form_el, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    )

    attachments = _extract_embedded_files(pdf, ATT_DIR, pdf_path.stem)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "form_type": "budget",
        "source_pdf": str(pdf_path),
        "source_sha256": sha256_file(pdf_path),
        "organization": org_name,
        "period_count": period_count,
        "extracted_xml": str(out_xml.relative_to(BASE)),
        "attachments": attachments,
    }
    print(f" ok  (org={org_name!r}, periods={period_count}, attachments={len(attachments)})")
    return record


def run(input_dir: Path | None = None) -> None:
    input_dir = input_dir or (BASE / "input-budget-pdfs")
    XML_DIR.mkdir(exist_ok=True)
    ATT_DIR.mkdir(exist_ok=True)
    AUDIT_DIR.mkdir(exist_ok=True)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {input_dir}")
        return

    print(f"Extracting {len(pdfs)} budget PDF(s) from {input_dir.relative_to(BASE)} …")
    with LOG_FILE.open("a") as log:
        for pdf_path in pdfs:
            try:
                record = extract_pdf(pdf_path)
                record["status"] = "ok"
            except Exception as exc:
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "form_type": "budget",
                    "source_pdf": str(pdf_path),
                    "status": "error",
                    "error": str(exc),
                }
                print(f" ERROR: {exc}")
            log.write(json.dumps(record) + "\n")

    print(f"\nExtraction complete. Log: {LOG_FILE.relative_to(BASE)}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run(path)
