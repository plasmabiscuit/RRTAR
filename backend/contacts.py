from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_contacts(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    entries = [item for item in (raw or {}).values() if isinstance(item, dict)]
    return sorted(entries, key=_contact_sort_key)


def search_contacts(contacts: List[Dict[str, Any]], query: str, limit: int) -> Dict[str, Any]:
    normalized_query = str(query or "").strip()
    max_results = max(1, min(int(limit or 24), 50))
    ranked = rank_contacts(contacts, normalized_query)
    results = []
    for index, contact in enumerate(ranked[:max_results]):
        results.append({
            "id": contact.get("email") or f'{contact.get("fullName") or "contact"}-{index}',
            "label": _contact_label(contact),
            "email": contact.get("email", ""),
            "jobTitle": contact.get("jobTitle", ""),
            "department": contact.get("department", ""),
            "unit": contact.get("unit", ""),
            "division": contact.get("Parent", ""),
            "workPhone": contact.get("workPhone", ""),
            "workLocation": contact.get("workLocation", ""),
            "campusBox": contact.get("campusBox", ""),
            "manifestEntry": build_keyperson_entry_from_contact(contact),
        })
    return {
        "query": normalized_query,
        "total": len(results),
        "results": results,
    }


def rank_contacts(contacts: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    if not query:
        return contacts
    needle = query.lower().strip()
    tokens = [token for token in needle.split() if token]
    ranked = []
    for contact in contacts:
        score = score_contact(contact, needle, tokens)
        if score > 0:
            ranked.append((score, contact))
    ranked.sort(key=lambda item: (-item[0], _contact_sort_key(item[1])))
    return [contact for _score, contact in ranked]


def score_contact(contact: Dict[str, Any], needle: str, tokens: List[str]) -> int:
    full_name = str(contact.get("fullName") or " ".join(filter(None, [
        contact.get("firstName"),
        contact.get("lastName"),
    ]))).strip()
    email = str(contact.get("email") or "")
    haystacks = [
        full_name,
        email,
        contact.get("department"),
        contact.get("unit"),
        contact.get("Parent"),
        contact.get("jobTitle"),
        contact.get("workLocation"),
        contact.get("campusBox"),
    ]
    lowered = [str(value or "").lower() for value in haystacks]

    score = 0
    if full_name.lower() == needle:
        score += 140
    if email.lower() == needle:
        score += 140
    if full_name.lower().startswith(needle):
        score += 110
    if email.lower().startswith(needle):
        score += 110
    if any(needle in value for value in lowered):
        score += 50
    for token in tokens:
        if any(token in value for value in lowered):
            score += 18
        else:
            score -= 12
    return score


def build_keyperson_entry_from_contact(contact: Dict[str, Any]) -> Dict[str, Any]:
    street2 = format_campus_box(contact.get("campusBox"))
    return {
        "source_pdf": "contacts.json",
        "source_element": "ContactDirectory",
        "source_index": 0,
        "target_action": "add_as_key_person",
        "exclude": False,
        "person": {
            "prefix": "",
            "first_name": contact.get("firstName", ""),
            "middle_name": "",
            "last_name": contact.get("lastName", ""),
            "suffix": "",
            "title": contact.get("jobTitle", ""),
            "organization_name": infer_organization_name(contact),
            "department": contact.get("department", ""),
            "division": contact.get("Parent", ""),
            "credential": "",
            "project_role": "",
            "other_project_role_category": "",
            "degree_type": "",
            "degree_year": "",
            "address": {
                "street1": "1 William L. Jones Dr" if street2 else "",
                "street2": street2,
                "city": "Cookeville",
                "county": "Putnam",
                "state": "TN: Tennessee",
                "province": "",
                "country": "",
                "postal_code": "388505-0001",
            },
            "phone": contact.get("workPhone", ""),
            "fax": "",
            "email": contact.get("email", ""),
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
                "Added from backend contacts; review role, address, email, and attachments before automate.",
            ],
        },
    }


def infer_organization_name(contact: Dict[str, Any]) -> str:
    email = str(contact.get("email") or "").lower()
    if email.endswith("@tntech.edu"):
        return "Tennessee Technological University"
    return ""


def format_campus_box(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.lower().startswith("campus box") else f"Campus Box {text}"


def _contact_label(contact: Dict[str, Any]) -> str:
    label = str(contact.get("fullName") or " ".join(filter(None, [
        contact.get("firstName"),
        contact.get("lastName"),
    ]))).strip()
    return label or str(contact.get("email") or "Unknown contact")


def _contact_sort_key(contact: Dict[str, Any]) -> str:
    return "\0".join([
        str(contact.get("lastName") or ""),
        str(contact.get("firstName") or ""),
        str(contact.get("email") or ""),
    ]).lower()
