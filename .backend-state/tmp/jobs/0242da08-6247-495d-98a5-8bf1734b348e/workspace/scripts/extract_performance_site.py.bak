"""
Extract XFA datasets XML and embedded attachments from Project/Performance Site PDFs.

Outputs:
  extracted-performance-site-xml/{stem}.xml
  extracted-performance-site-attachments/{filename}
  audit/run_log.jsonl
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pikepdf
from lxml import etree

BASE = Path(__file__).resolve().parents[1]
XML_DIR = BASE / "extracted-performance-site-xml"
ATT_DIR = BASE / "extracted-performance-site-attachments"
AUDIT_DIR = BASE / "audit"
LOG_FILE = AUDIT_DIR / "run_log.jsonl"

FORM_NS = "http://apply.grants.gov/forms/PerformanceSite_4_0-V4.0"
FORM_LOCAL = "PerformanceSite_4_0"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def safe_filename(s: str) -> str:
    return re.sub(r"[^\w.\-\[\]]", "_", s)


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

        ext = ".pdf"
        try:
            fname_obj = file_spec.F
            fname = str(fname_obj)
            suffix = Path(fname).suffix
            if suffix:
                ext = suffix
        except Exception:
            pass

        base = f"{stem}_{safe_filename(desc)}{ext}"
        dest = att_dir / base
        if dest.exists():
            for n in range(2, 100):
                alt = att_dir / f"{stem}_{safe_filename(desc)}_{n}{ext}"
                if not alt.exists():
                    dest = alt
                    break
        dest.write_bytes(data)
        results.append({"key": key, "desc": desc, "path": str(dest.relative_to(BASE))})

    return results


def _count_other_sites(form_el: etree._Element) -> int:
    return len(form_el.findall(f"{{{FORM_NS}}}OtherSite"))


def extract_pdf(pdf_path: Path) -> dict:
    print(f"  {pdf_path.name} …", end="", flush=True)
    XML_DIR.mkdir(parents=True, exist_ok=True)
    ATT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    pdf = pikepdf.open(pdf_path)
    packets = _get_xfa_array(pdf)
    datasets_bytes = _find_datasets(packets)
    form_el = _extract_form_element(datasets_bytes)

    out_xml = XML_DIR / f"{pdf_path.stem}.xml"
    out_xml.write_bytes(
        etree.tostring(form_el, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    )
    attachments = _extract_embedded_files(pdf, ATT_DIR, pdf_path.stem)
    other_site_count = _count_other_sites(form_el)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "form_type": "performance_site",
        "source_pdf": str(pdf_path),
        "source_sha256": sha256_file(pdf_path),
        "other_site_count": other_site_count,
        "extracted_xml": str(out_xml.relative_to(BASE)),
        "attachments": attachments,
    }
    print(f" ok  (other_sites={other_site_count}, attachments={len(attachments)})")
    return record


def run(input_dir: Path | None = None) -> None:
    input_dir = input_dir or (BASE / "input-performance-site-pdfs")
    XML_DIR.mkdir(exist_ok=True)
    ATT_DIR.mkdir(exist_ok=True)
    AUDIT_DIR.mkdir(exist_ok=True)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {input_dir}")
        return

    try:
        display_dir = input_dir.relative_to(BASE)
    except ValueError:
        display_dir = input_dir
    print(f"Extracting {len(pdfs)} performance site PDF(s) from {display_dir} …")
    with LOG_FILE.open("a") as log:
        for pdf_path in pdfs:
            try:
                record = extract_pdf(pdf_path)
                record["status"] = "ok"
            except Exception as exc:
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "form_type": "performance_site",
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
