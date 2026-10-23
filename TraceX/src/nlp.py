from __future__ import annotations

import re
from typing import Dict, List

import spacy

# Load the model required for the existing entity extraction behavior.
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    try:
        import spacy.cli
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    except Exception as exc:
        raise RuntimeError(
            "threadVault requires the en_core_web_sm spaCy model. Install dependencies from requirements.txt."
        ) from exc


PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s\-.]*)?(?:\d[\s\-.]*){6,14}")
VEHICLE_RE = re.compile(r"[A-Z0-9]{2,3}[\s\-]?[A-Z0-9]{1,4}")
VEHICLE_WORD_RE = re.compile(r"\bvehicle[\s\-]?\d{1,4}\b", re.I)
ACCOUNT_RE = re.compile(r"[A-Za-z0-9]{6,30}")


def normalize_person(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    # keep last 10 digits if longer (common mobile formats)
    if len(digits) > 10:
        digits = digits[-10:]
    return digits


def normalize_vehicle(veh: str) -> str:
    s = (veh or "").upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def normalize_account(acc: str) -> str:
    s = (acc or "").upper()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def normalize_org_loc(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_entities_from_text(text: str, source: str, record_id: str, case_id: str) -> List[Dict]:
    entities: List[Dict] = []
    if not text:
        return entities

    # spaCy NER - conservative handling: collect PERSON norms first
    person_norms = set()
    if nlp is not None:
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                person_norms.add(normalize_person(ent.text))

        for ent in doc.ents:
            ent_type = ent.label_
            raw = ent.text
            # If spaCy labels ORG but the same token matches a PERSON norm, prefer PERSON
            if ent_type == "ORG" and normalize_person(raw) in person_norms:
                norm = normalize_person(raw)
                e_type = "PERSON"
            elif ent_type == "PERSON":
                norm = normalize_person(raw)
                e_type = "PERSON"
            elif ent_type in ("GPE", "LOC"):
                norm = normalize_org_loc(raw)
                e_type = "LOCATION"
            elif ent_type == "ORG":
                norm = normalize_org_loc(raw)
                e_type = "ORGANIZATION"
            else:
                continue

            entities.append(
                {
                    "entity_type": e_type,
                    "raw_value": raw,
                    "normalized_value": norm,
                    "source": source,
                    "record_id": record_id,
                    "case_id": case_id,
                }
            )

    # Regex-based phones
    for m in PHONE_RE.finditer(text):
        raw = m.group(0)
        norm = normalize_phone(raw)
        if norm:
            entities.append(
                {
                    "entity_type": "PHONE",
                    "raw_value": raw,
                    "normalized_value": norm,
                    "source": source,
                    "record_id": record_id,
                    "case_id": case_id,
                }
            )

    # Vehicles - pattern-based (both plate-like and 'Vehicle-17' style)
    for m in VEHICLE_RE.finditer(text):
        raw = m.group(0)
        if re.search(r"[A-Za-z]", raw) and re.search(r"\d", raw):
            norm = normalize_vehicle(raw)
            entities.append(
                {
                    "entity_type": "VEHICLE",
                    "raw_value": raw,
                    "normalized_value": norm,
                    "source": source,
                    "record_id": record_id,
                    "case_id": case_id,
                }
            )
    for m in VEHICLE_WORD_RE.finditer(text):
        raw = m.group(0)
        norm = normalize_vehicle(raw)
        entities.append(
            {
                "entity_type": "VEHICLE",
                "raw_value": raw,
                "normalized_value": norm,
                "source": source,
                "record_id": record_id,
                "case_id": case_id,
            }
        )

    # Accounts (simple heuristic: medium-length alnum tokens)
    for m in ACCOUNT_RE.finditer(text):
        raw = m.group(0)
        if len(raw) >= 6 and any(c.isdigit() for c in raw):
            norm = normalize_account(raw)
            entities.append(
                {
                    "entity_type": "ACCOUNT",
                    "raw_value": raw,
                    "normalized_value": norm,
                    "source": source,
                    "record_id": record_id,
                    "case_id": case_id,
                }
            )

    return entities


def extract_entities_from_row(dataset: str, row: Dict, case_id: str) -> List[Dict]:
    # Build representative text depending on dataset
    if dataset == "fir":
        record_id = str(row.get("fir_id", "fir_unknown"))
        text = " ".join([str(row.get("description", "")), str(row.get("location", ""))])
    elif dataset == "cdr":
        record_id = str(row.get("cdr_id", "cdr_unknown"))
        text = " ".join([str(row.get("caller", "")), str(row.get("receiver", ""))])
    elif dataset == "transactions":
        record_id = str(row.get("transaction_id", "txn_unknown"))
        text = " ".join([str(row.get("sender", "")), str(row.get("receiver", "")), str(row.get("description", ""))])
    elif dataset == "social":
        record_id = str(row.get("post_id", "post_unknown"))
        text = " ".join([str(row.get("author", "")), str(row.get("mentioned_person", "")), str(row.get("location", "")), str(row.get("content", ""))])
    else:
        record_id = "unknown"
        text = " ".join([str(v) for v in row.values()])

    entities = extract_entities_from_text(text, dataset, record_id, case_id)

    # Conservative additional extractions from structured fields
    try:
        if dataset == "fir":
            loc = str(row.get("location", "")).strip()
            if loc:
                entities.append({
                    "entity_type": "LOCATION",
                    "raw_value": loc,
                    "normalized_value": normalize_org_loc(loc),
                    "source": dataset,
                    "record_id": record_id,
                    "case_id": case_id,
                })

        if dataset == "social":
            loc = str(row.get("location", "")).strip()
            if loc:
                entities.append({
                    "entity_type": "LOCATION",
                    "raw_value": loc,
                    "normalized_value": normalize_org_loc(loc),
                    "source": dataset,
                    "record_id": record_id,
                    "case_id": case_id,
                })

        if dataset == "cdr":
            caller = str(row.get("caller", "")).strip()
            receiver = str(row.get("receiver", "")).strip()
            for val in (caller, receiver):
                if not val:
                    continue
                # phone in caller/receiver
                for m in PHONE_RE.finditer(val):
                    raw = m.group(0)
                    norm = normalize_phone(raw)
                    if norm:
                        entities.append({
                            "entity_type": "PHONE",
                            "raw_value": raw,
                            "normalized_value": norm,
                            "source": dataset,
                            "record_id": record_id,
                            "case_id": case_id,
                        })
                # vehicle tokens
                if VEHICLE_WORD_RE.search(val) or VEHICLE_RE.search(val):
                    raw = val
                    norm = normalize_vehicle(raw)
                    entities.append({
                        "entity_type": "VEHICLE",
                        "raw_value": raw,
                        "normalized_value": norm,
                        "source": dataset,
                        "record_id": record_id,
                        "case_id": case_id,
                    })

        if dataset == "transactions":
            sender = str(row.get("sender", "")).strip()
            receiver = str(row.get("receiver", "")).strip()
            desc = str(row.get("description", "")).strip()
            for val in (sender, receiver, desc):
                if not val:
                    continue
                for m in PHONE_RE.finditer(val):
                    raw = m.group(0)
                    norm = normalize_phone(raw)
                    if norm:
                        entities.append({
                            "entity_type": "PHONE",
                            "raw_value": raw,
                            "normalized_value": norm,
                            "source": dataset,
                            "record_id": record_id,
                            "case_id": case_id,
                        })
                for m in ACCOUNT_RE.finditer(val):
                    raw = m.group(0)
                    if len(raw) >= 6 and any(c.isdigit() for c in raw):
                        norm = normalize_account(raw)
                        entities.append({
                            "entity_type": "ACCOUNT",
                            "raw_value": raw,
                            "normalized_value": norm,
                            "source": dataset,
                            "record_id": record_id,
                            "case_id": case_id,
                        })
    except Exception:
        # conservative: do not fail extraction on unexpected fields
        pass

    return entities
