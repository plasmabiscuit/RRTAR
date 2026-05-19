"""Download and checksum-pin the four Grants.gov dependency XSDs into schemas/."""

import hashlib
import json
import sys
from pathlib import Path

import requests

SCHEMAS = {
    "Attachments-V1.0.xsd":   "https://apply07.grants.gov/apply/system/schemas/Attachments-V1.0.xsd",
    "Global-V1.0.xsd":        "https://apply07.grants.gov/apply/system/schemas/Global-V1.0.xsd",
    "GlobalLibrary-V2.0.xsd": "https://apply07.grants.gov/apply/system/schemas/GlobalLibrary-V2.0.xsd",
    "UniversalCodes-V2.0.xsd":"https://apply07.grants.gov/apply/system/schemas/UniversalCodes-V2.0.xsd",
}

BASE = Path(__file__).resolve().parents[1]
SCHEMA_DIR = BASE / "schemas"
VERSION_FILE = BASE / "config" / "form_version.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_pins() -> dict:
    cfg = json.loads(VERSION_FILE.read_text())
    return cfg.get("xsd_checksums_sha256", {})


def save_pins(pins: dict) -> None:
    cfg = json.loads(VERSION_FILE.read_text())
    cfg["xsd_checksums_sha256"] = pins
    VERSION_FILE.write_text(json.dumps(cfg, indent=2) + "\n")


def fetch(force: bool = False) -> None:
    SCHEMA_DIR.mkdir(exist_ok=True)
    pins = load_pins()
    updated = dict(pins)
    errors = []

    for filename, url in SCHEMAS.items():
        dest = SCHEMA_DIR / filename
        if dest.exists() and not force:
            actual = sha256(dest.read_bytes())
            if filename in pins:
                if actual != pins[filename]:
                    errors.append(
                        f"CHECKSUM MISMATCH for {filename}: "
                        f"expected {pins[filename]}, got {actual}. "
                        "Run with --force to re-download."
                    )
                else:
                    print(f"  ok  {filename}")
                continue
            # File exists but no pin yet — pin it.
            updated[filename] = actual
            print(f"  pinned  {filename}  {actual[:16]}…")
            continue

        print(f"  downloading {filename} …", end="", flush=True)
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.content
        digest = sha256(data)

        if filename in pins and digest != pins[filename]:
            errors.append(
                f"REMOTE CHECKSUM MISMATCH for {filename}: "
                f"expected {pins[filename]}, got {digest}. "
                "The upstream schema may have changed. Review before proceeding."
            )
            print(" MISMATCH")
            continue

        dest.write_bytes(data)
        updated[filename] = digest
        print(f" done  {digest[:16]}…")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    save_pins(updated)
    print("All schemas present and pinned.")


if __name__ == "__main__":
    force = "--force" in sys.argv
    fetch(force=force)
