from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Set

from .nlp import extract_entities_from_row, normalize_person
from difflib import SequenceMatcher
from .ingestion import load_case


@dataclass
class CanonicalEntity:
    canonical_id: str
    entity_type: str
    canonical_name: str
    aliases: Set[str] = field(default_factory=set)
    source_records: List[Dict] = field(default_factory=list)
    case_ids: Set[str] = field(default_factory=set)


class Resolver:
    def __init__(self):
        self.counters = defaultdict(int)
        # mapping: entity_type -> normalized_value -> canonical_id
        self.map = defaultdict(dict)
        self.canonical: Dict[str, CanonicalEntity] = {}

    def _next_id(self, entity_type: str) -> str:
        t = entity_type.upper()
        self.counters[t] += 1
        return f"{t}_{self.counters[t]:03d}"

    def _fuzzy_match_person(self, norm_name: str) -> str | None:
        # conservative fuzzy matching among existing PERSON entries
        best_id = None
        best_score = 0.0
        for norm, cid in self.map.get("PERSON", {}).items():
            # consider substring matches as strong signal
            if norm_name in norm or norm in norm_name:
                return cid
            score = SequenceMatcher(None, norm_name, norm).ratio()
            if score > best_score:
                best_score = score
                best_id = cid
        # threshold conservative
        if best_score >= 0.92:
            return best_id
        return None

    def add_entity(self, ent: Dict):
        et = ent["entity_type"]
        norm = ent["normalized_value"]
        raw = ent["raw_value"]
        source = ent.get("source")
        record_id = ent.get("record_id")
        case_id = ent.get("case_id")

        # exact match
        existing = self.map.get(et, {}).get(norm)
        if existing:
            cid = existing
        else:
            # person fuzzy
            if et == "PERSON":
                fuzzy = self._fuzzy_match_person(norm)
                if fuzzy:
                    cid = fuzzy
                else:
                    cid = self._next_id(et)
            else:
                cid = self._next_id(et)

            # register mapping
            self.map[et][norm] = cid
            # create canonical entity only if this cid is new (avoid overwriting existing canonical)
            if cid not in self.canonical:
                canonical_name = raw if raw else norm
                self.canonical[cid] = CanonicalEntity(canonical_id=cid, entity_type=et, canonical_name=canonical_name)

        # update canonical entity
        ce = self.canonical[cid]
        incoming_alias = ent.get("raw_value") or ent.get("normalized_value")
        ce.aliases.add(incoming_alias)
        ce.source_records.append({"source": source, "record_id": record_id, "raw_value": raw})
        if case_id:
            ce.case_ids.add(case_id)

        # Prefer most-informative full-name for PERSON canonical_name
        if et == "PERSON":
            candidate = (raw or norm or "").strip()
            current = (ce.canonical_name or "").strip()
            if candidate:
                # If candidate contains a space and current does not, prefer candidate
                if (" " in candidate) and (" " not in current):
                    ce.canonical_name = candidate
                else:
                    # prefer more words, then longer length
                    cand_words = len(candidate.split())
                    curr_words = len(current.split())
                    if cand_words > curr_words:
                        ce.canonical_name = candidate
                    elif cand_words == curr_words and len(candidate) > len(current):
                        ce.canonical_name = candidate

        return cid


def process_case(case_id: str) -> Dict:
    case = load_case(case_id)
    datasets = case["datasets"]

    resolver = Resolver()
    extracted = []

    for ds_name, df in datasets.items():
        for _, row in df.iterrows():
            ents = extract_entities_from_row(ds_name, row.to_dict(), case_id)
            for e in ents:
                extracted.append(e)
                resolver.add_entity(e)

    # Post-process extracted entities: conservative reclassification
    # If an entity was labeled ORGANIZATION but its normalized form matches a PERSON normalized value seen elsewhere, reclassify to PERSON
    person_norms = {e['normalized_value'] for e in extracted if e['entity_type'] == 'PERSON' and e.get('normalized_value')}
    for e in extracted:
        if e['entity_type'] == 'ORGANIZATION':
            raw_norm = normalize_person(e.get('raw_value') or '')
            if not raw_norm:
                continue
            # direct match
            if raw_norm in person_norms:
                match = True
            else:
                # conservative fuzzy/substring match against known person norms
                match = False
                for pn in person_norms:
                    if raw_norm in pn or pn in raw_norm:
                        match = True
                        break
                    score = SequenceMatcher(None, raw_norm, pn).ratio()
                    if score >= 0.9:
                        match = True
                        break
            if match:
                e['entity_type'] = 'PERSON'
                e['normalized_value'] = raw_norm
                resolver.add_entity(e)

    # prepare summary
    by_type = defaultdict(int)
    for cid, ce in resolver.canonical.items():
        by_type[ce.entity_type] += 1

    return {
        "case_id": case_id,
        "extracted_entities": extracted,
        "canonical_entities": resolver.canonical,
        "counts": {
            "total_extracted": len(extracted),
            "total_canonical": len(resolver.canonical),
            "by_type": dict(by_type),
        },
    }
