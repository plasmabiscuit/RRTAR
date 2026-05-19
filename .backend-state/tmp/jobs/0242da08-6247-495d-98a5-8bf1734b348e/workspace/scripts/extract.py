from __future__ import annotations

"""
Extract XFA datasets XML and embedded attachments from subrecipient R&R Key Person PDFs.

Outputs:
  extracted-xml/{stem}.xml            — clean RR_KeyPersonExpanded_4_0 element
  extracted-attachments/{desc}.pdf    — embedded biosketches and support docs
  audit/run_log.jsonl                 — one JSON line per PDF processed
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pikepdf
from lxml import etree

BASE = Path(__file__).resolve().parents[1]
XML_DIR = BASE / "extracted-xml"
ATT_DIR = BASE / "extracted-attachments"
AUDIT_DIR = BASE / "audit"
LOG_FILE = AUDIT_DIR / "run_log.jsonl"

XFA_NS = "http://www.xfa.org/schema/xfa-data/1.0/"
FORM_LOCAL = "RR_KeyPersonExpanded_4_0"
FORM_NS = "http://apply.grants.gov/forms/RR_KeyPersonExpanded_4_0-V4.0"
GLOB_LIB_NS = "http://apply.grants.gov/system/GlobalLibrary-V2.0"

# Matches the record-type+index portion of a /Desc string, e.g. "PDPI[0]" or "KeyPerson[2]"
_DESC_RECORD_RE = re.compile(r"\.(PDPI|KeyPerson)\[(\d+)\]\.")

# Maps (record_type, slot_suffix) → short human label for the output filename
_SLOT_LABELS: Dict[Tuple[str, str], str] = {
    ("PDPI",      "mandatoryFile0"): "Biosketch",
    ("PDPI",      "optionalFile0"):  "Current_Pending",
    ("KeyPerson", "optionalFile0"):  "Biosketch",
    ("KeyPerson", "optionalFile1"):  "Current_Pending",
}


def _slot_label(desc: str) -> Optional[str]:
    """Return 'Biosketch' or 'Current_Pending' from a /Desc string, or None."""
    m = _DESC_RECORD_RE.search(desc)
    if not m:
        return None
    slot = desc.rsplit(".", 1)[-1]
    return _SLOT_LABELS.get((m.group(1), slot))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def safe_filename(s: str) -> str:
    return re.sub(r"[^\w.\-\[\]]", "_", s)


def _get_xfa_array(pdf: pikepdf.Pdf) -> List[Tuple[str, bytes]]:
    """Return a list of (name, bytes) tuples from the XFA array, or a single-item list."""
    xfa = pdf.Root.AcroForm.XFA
    if isinstance(xfa, pikepdf.Stream):
        return [("single", bytes(xfa.read_bytes()))]
    # Array of name/stream pairs
    packets = []
    items = list(xfa)
    if len(items) % 2 != 0:
        print(f"  WARNING: XFA array has odd length ({len(items)}); last item dropped", flush=True)
    for i in range(0, len(items) - 1, 2):
        name = str(items[i])
        stream = items[i + 1]
        packets.append((name, bytes(stream.read_bytes())))
    return packets


def _find_datasets(packets: List[Tuple[str, bytes]]) -> bytes:
    """Return the bytes of the 'datasets' XFA packet."""
    # Try by name first
    for name, data in packets:
        if name == "datasets":
            return data
    # Fall back to scanning for xfa:datasets root element
    for _name, data in packets:
        if b"xfa:datasets" in data or b"<datasets" in data:
            return data
    raise ValueError("Could not locate XFA datasets packet")


def _text_score(el: etree._Element) -> int:
    """Count non-empty text nodes below an element."""
    return sum(1 for text in el.xpath(".//text()") if (text or "").strip())


def _is_keyperson_form(localname: str) -> bool:
    return localname.startswith("RR_KeyPerson")


def _extract_form_element(datasets_bytes: bytes) -> etree._Element:
    """Parse datasets XML and return the most likely populated key-person form element."""
    root = etree.fromstring(datasets_bytes)
    candidates = []
    preferred = []
    for el in root.iter():
        qname = etree.QName(el.tag)
        local = qname.localname
        if not _is_keyperson_form(local):
            continue
        score = _text_score(el)
        entry = (score, local == FORM_LOCAL, local.startswith("RR_KeyPersonExpanded"), el)
        candidates.append(entry)
        if local == FORM_LOCAL:
            preferred.append(entry)

    if not candidates:
        raise ValueError("No RR_KeyPerson* form element found in datasets packet")

    # Prefer populated forms first, then the exact 4.0 expanded form, then any expanded variant.
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    chosen = candidates[0][3]

    # If the exact 4.0 form exists and is populated, keep preferring it.
    populated_preferred = [item for item in preferred if item[0] > 0]
    if populated_preferred:
        chosen = sorted(populated_preferred, key=lambda item: item[0], reverse=True)[0][3]

    return chosen


def _build_person_name_map(form_el: etree._Element) -> Dict[str, str]:
    """Return {"PDPI[0]": "Anton", "KeyPerson[0]": "Zhan", ...} for last-name prefixing."""
    name_map: Dict[str, str] = {}
    form_ns = etree.QName(form_el.tag).namespace
    kp_idx = 0
    for child in form_el:
        local = etree.QName(child.tag).localname
        if local not in ("PDPI", "KeyPerson"):
            continue
        profile = child.find(f"{{{form_ns}}}Profile")
        last_name = ""
        if profile is not None:
            name_el = profile.find(f"{{{form_ns}}}Name")
            if name_el is not None:
                ln = name_el.find(f"{{{GLOB_LIB_NS}}}LastName")
                if ln is not None and ln.text:
                    last_name = ln.text.strip()
        if local == "PDPI":
            name_map["PDPI[0]"] = last_name
        else:
            name_map[f"KeyPerson[{kp_idx}]"] = last_name
            kp_idx += 1
    return name_map


def _extract_embedded_files(
    pdf: pikepdf.Pdf,
    att_dir: Path,
    name_map: Optional[Dict[str, str]] = None,
) -> List[dict]:
    """Extract all embedded files from /Root/Names/EmbeddedFiles/Names.

    Filenames are prefixed with the person's last name when name_map is provided,
    e.g. Anton_RR_KeyPersonExpanded_4_0_P1.PDPI[0].mandatoryFile0.pdf
    """
    results = []
    try:
        names_tree = pdf.Root.Names.EmbeddedFiles.Names
    except AttributeError:
        return results

    items = list(names_tree)
    for i in range(0, len(items), 2):
        key = str(items[i])
        file_spec = items[i + 1]

        desc = key  # fallback
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

        # Derive last-name prefix from the /Desc record key
        last_name = ""
        if name_map:
            m = _DESC_RECORD_RE.search(desc)
            if m:
                record_key = f"{m.group(1)}[{m.group(2)}]"
                last_name = name_map.get(record_key, "")

        label = _slot_label(desc)
        if label:
            base = f"{last_name}-{label}.pdf" if last_name else f"{label}.pdf"
            # Resolve collision when two people share a last name in the same batch
            if (att_dir / base).exists():
                stem = base[:-4]
                resolved = False
                for _n in range(2, 100):
                    alt = f"{stem}_{_n}.pdf"
                    if not (att_dir / alt).exists():
                        base = alt
                        resolved = True
                        break
                if not resolved:
                    print(f"  WARNING: could not find a free filename for '{base}'; overwriting", flush=True)
            fname = base
        else:
            safe_desc = safe_filename(desc) + ".pdf"
            fname = f"{last_name}_{safe_desc}" if last_name else safe_desc
        dest = att_dir / fname
        dest.write_bytes(data)
        results.append({"key": key, "desc": desc, "last_name": last_name,
                        "path": str(dest.relative_to(BASE))})

    return results


def _count_persons(form_el: etree._Element) -> Tuple[int, int]:
    pdpi_count = 0
    kp_count = 0
    for child in form_el:
        local = etree.QName(child.tag).localname
        if local == "PDPI":
            pdpi_count += 1
        elif local == "KeyPerson":
            kp_count += 1
    return pdpi_count, kp_count


def extract_pdf(pdf_path: Path) -> dict:
    """Extract one PDF and return an audit record."""
    print(f"  {pdf_path.name} …", end="", flush=True)

    pdf = pikepdf.open(pdf_path)
    packets = _get_xfa_array(pdf)
    datasets_bytes = _find_datasets(packets)
    form_el = _extract_form_element(datasets_bytes)
    form_qname = etree.QName(form_el.tag)
    form_ns = form_qname.namespace

    # FormVersion is namespace-qualified in actual PDFs
    version = form_el.get(f"{{{form_ns}}}FormVersion") or form_el.get("FormVersion") or "unknown"

    out_xml = XML_DIR / (pdf_path.stem + ".xml")
    out_xml.write_bytes(etree.tostring(form_el, pretty_print=True, xml_declaration=True, encoding="UTF-8"))

    name_map = _build_person_name_map(form_el)
    attachments = _extract_embedded_files(pdf, ATT_DIR, name_map)
    pdpi_count, kp_count = _count_persons(form_el)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_pdf": str(pdf_path),
        "source_sha256": sha256_file(pdf_path),
        "form_version": version,
        "form_local_name": form_qname.localname,
        "form_namespace": form_ns,
        "pdpi_count": pdpi_count,
        "key_person_count": kp_count,
        "extracted_xml": str(out_xml.relative_to(BASE)),
        "attachments": attachments,
    }
    print(f" ok  (PDPI={pdpi_count}, KeyPerson={kp_count}, attachments={len(attachments)})")
    return record


def run(input_dir: Optional[Path] = None) -> None:
    input_dir = input_dir or (BASE / "input-pdfs")
    XML_DIR.mkdir(exist_ok=True)
    ATT_DIR.mkdir(exist_ok=True)
    AUDIT_DIR.mkdir(exist_ok=True)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {input_dir}")
        return

    with LOG_FILE.open("a") as log:
        for pdf_path in pdfs:
            try:
                record = extract_pdf(pdf_path)
                record["status"] = "ok"
            except Exception as exc:
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
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
