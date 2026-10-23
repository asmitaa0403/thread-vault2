from __future__ import annotations

from typing import Dict, Tuple, Optional
import networkx as nx
from datetime import datetime

from .ingestion import load_case
from .entity_resolution import process_case
from .nlp import normalize_person, normalize_org_loc


def _parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
    if not ts or str(ts).strip() == "":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(ts), fmt)
        except Exception:
            continue
    return None


def _build_alias_map(canonical_entities: Dict) -> Dict[str, str]:
    # map normalized alias -> canonical_id for quick lookup
    amap = {}
    for cid, ce in canonical_entities.items():
        for a in ce.aliases:
            key = a.strip()
            if not key:
                continue
            # try person normalizer first
            p = normalize_person(key)
            amap[("PERSON", p)] = cid
            # org/location normalizer
            o = normalize_org_loc(key)
            amap[("ORG", o)] = cid
            amap[("LOC", o)] = cid
            # also raw lowercase fallback
            amap[("RAW", key.lower())] = cid
    return amap


def _lookup_cid(name: str, amap: Dict) -> Optional[str]:
    if not name:
        return None
    p = normalize_person(name)
    cid = amap.get(("PERSON", p))
    if cid:
        return cid
    o = normalize_org_loc(name)
    cid = amap.get(("ORG", o)) or amap.get(("LOC", o))
    if cid:
        return cid
    cid = amap.get(("RAW", name.lower()))
    return cid


def build_case_graph(case_id: str) -> nx.Graph:
    """Build a NetworkX graph for a case using canonical entities as nodes

    Nodes are canonical entities (from process_case). Edges are added only
    when both endpoints map to canonical entities using observed records.
    """
    case = load_case(case_id)
    proc = process_case(case_id)
    canonical = proc["canonical_entities"]

    G = nx.Graph()

    # add nodes
    for cid, ce in canonical.items():
        G.add_node(cid, canonical_id=cid, entity_type=ce.entity_type, canonical_name=ce.canonical_name)

    # prepare alias map
    amap = _build_alias_map(canonical)

    # process CDR (calls)
    for _, row in case["datasets"]["cdr"].iterrows():
        caller = str(row.get("caller", "")).strip()
        receiver = str(row.get("receiver", "")).strip()
        c_cid = _lookup_cid(caller, amap)
        r_cid = _lookup_cid(receiver, amap)
        if not c_cid or not r_cid:
            continue
        ts = _parse_timestamp(row.get("timestamp"))
        rec_id = str(row.get("cdr_id"))
        G.add_edge(c_cid, r_cid, relationship_type="CALLED", source="cdr", record_id=rec_id, timestamp=ts, case_id=case_id)

    # process transactions (payments)
    for _, row in case["datasets"]["transactions"].iterrows():
        sender = str(row.get("sender", "")).strip()
        receiver = str(row.get("receiver", "")).strip()
        s_cid = _lookup_cid(sender, amap)
        r_cid = _lookup_cid(receiver, amap)
        if not s_cid or not r_cid:
            continue
        ts = _parse_timestamp(row.get("timestamp"))
        rec_id = str(row.get("transaction_id"))
        amount = row.get("amount")
        G.add_edge(s_cid, r_cid, relationship_type="PAID", source="transactions", record_id=rec_id, timestamp=ts, amount=amount, case_id=case_id)

    # social: TAGGED_WITH and SEEN_AT
    for _, row in case["datasets"]["social"].iterrows():
        author = str(row.get("author", "")).strip()
        mentioned = str(row.get("mentioned_person", "")).strip()
        loc = str(row.get("location", "")).strip()
        a_cid = _lookup_cid(author, amap)
        m_cid = _lookup_cid(mentioned, amap)
        loc_cid = _lookup_cid(loc, amap)
        ts = _parse_timestamp(row.get("timestamp"))
        rec_id = str(row.get("post_id"))
        if a_cid and m_cid:
            G.add_edge(a_cid, m_cid, relationship_type="TAGGED_WITH", source="social", record_id=rec_id, timestamp=ts, case_id=case_id)
        if a_cid and loc_cid:
            G.add_edge(a_cid, loc_cid, relationship_type="SEEN_AT", source="social", record_id=rec_id, timestamp=ts, case_id=case_id)

    # FIR: associate persons seen at location and co-mentioned associations
    # For FIR, use extracted PERSON entries from process_case to avoid inventing names
    extracted = proc["extracted_entities"]
    fir_rows = case["datasets"]["fir"]
    for _, row in fir_rows.iterrows():
        rec_id = str(row.get("fir_id"))
        loc = str(row.get("location", "")).strip()
        loc_cid = _lookup_cid(loc, amap)
        # persons mentioned in this FIR
        persons = [e for e in extracted if e["source"] == "fir" and e["record_id"] == rec_id and e["entity_type"] == "PERSON"]
        person_cids = []
        for p in persons:
            cid = _lookup_cid(p.get("raw_value") or p.get("normalized_value"), amap)
            if cid:
                person_cids.append(cid)
                if loc_cid:
                    G.add_edge(cid, loc_cid, relationship_type="SEEN_AT", source="fir", record_id=rec_id, timestamp=_parse_timestamp(row.get("date")), case_id=case_id)
        # associations between co-mentioned persons
        for i in range(len(person_cids)):
            for j in range(i + 1, len(person_cids)):
                a = person_cids[i]
                b = person_cids[j]
                G.add_edge(a, b, relationship_type="ASSOCIATED_WITH", source="fir", record_id=rec_id, timestamp=_parse_timestamp(row.get("date")), case_id=case_id)

    return G
