from __future__ import annotations

from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime, timedelta

from .ingestion import load_case
from .graph import build_case_graph
from .nlp import normalize_person


def _parse_ts(ts: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(ts), fmt)
        except Exception:
            continue
    raise ValueError("Unrecognized timestamp")


def detect_patterns(case_id: str) -> List[Dict[str, Any]]:
    case = load_case(case_id)
    G = build_case_graph(case_id)
    patterns: List[Dict[str, Any]] = []

    # RULE 1: HIGH CALL FREQUENCY (>5 calls within 3 days between same pair)
    calls_by_pair = defaultdict(list)
    for _, row in case["datasets"]["cdr"].iterrows():
        a = str(row.get("caller", "")).strip()
        b = str(row.get("receiver", "")).strip()
        ts = _parse_ts(row.get("timestamp"))
        key = tuple(sorted([normalize_person(a), normalize_person(b)]))
        calls_by_pair[key].append((ts, row.get("cdr_id"), a, b))

    for key, events in calls_by_pair.items():
        events.sort()
        times = [e[0] for e in events]
        # sliding window
        i = 0
        for j in range(len(times)):
            while times[j] - times[i] > timedelta(days=3):
                i += 1
            window_count = j - i + 1
            if window_count > 5:
                ev_slice = events[i : j + 1]
                # preserve order and deduplicate entities
                entities = []
                for ev in ev_slice:
                    for name in (ev[2], ev[3]):
                        if name and name not in entities:
                            entities.append(name)
                patterns.append(
                    {
                        "pattern_id": f"HIGH_CALL_FREQ::{case_id}::{key[0]}::{key[1]}::{i}",
                        "case_id": case_id,
                        "pattern_type": "HIGH_CALL_FREQUENCY",
                        "severity": "high" if window_count > 10 else "medium",
                        "entities_involved": entities,
                        "evidence": [e[1] for e in ev_slice],
                        "timestamp": times[j].isoformat(),
                        "explanation": f"{window_count} calls between {entities} within 3 days.",
                    }
                )
                break

    # RULE 2: CALL FOLLOWED BY TRANSACTION within 24 hours
    # Build mapping of normalized person names to call timestamps and transactions
    calls_map = defaultdict(list)
    for _, row in case["datasets"]["cdr"].iterrows():
        a = str(row.get("caller", "")).strip()
        b = str(row.get("receiver", "")).strip()
        ts = _parse_ts(row.get("timestamp"))
        calls_map[(normalize_person(a), normalize_person(b))].append((ts, row.get("cdr_id"), a, b))

    for _, row in case["datasets"]["transactions"].iterrows():
        sender = str(row.get("sender", "")).strip()
        receiver = str(row.get("receiver", "")).strip()
        t_ts = _parse_ts(row.get("timestamp"))
        txn_id = row.get("transaction_id")
        # check both directions
        for pair in [(normalize_person(sender), normalize_person(receiver)), (normalize_person(receiver), normalize_person(sender))]:
            for call in calls_map.get(pair, []):
                call_ts = call[0]
                if timedelta(0) <= (t_ts - call_ts) <= timedelta(hours=24):
                    patterns.append(
                        {
                            "pattern_id": f"CALL_TXN::{case_id}::{pair[0]}::{pair[1]}::{txn_id}",
                            "case_id": case_id,
                            "pattern_type": "CALL_FOLLOWED_BY_TRANSACTION",
                            "severity": "high",
                            # preserve order and deduplicate entities involved while keeping evidence
                            "entities_involved": list(dict.fromkeys([call[2], call[3], sender, receiver])),
                            "evidence": {"call_id": call[1], "transaction_id": txn_id},
                            "timestamp": t_ts.isoformat(),
                            "explanation": f"Call between {call[2]} and {call[3]} at {call_ts.isoformat()} followed by transaction {txn_id} at {t_ts.isoformat()}.",
                        }
                    )

    # RULE 3: CROSS-SOURCE PRESENCE (appearing in 3 or more source types)
    # Use process_case extracted entities
    from .entity_resolution import process_case

    proc = process_case(case_id)
    extracted = proc["extracted_entities"]
    sources_by_entity = defaultdict(set)
    for e in extracted:
        name = e.get("normalized_value") or e.get("raw_value")
        sources_by_entity[name].add(e.get("source"))

    for name, srcs in sources_by_entity.items():
        if len(srcs) >= 3:
            patterns.append(
                {
                    "pattern_id": f"CROSS_SOURCE::{case_id}::{name}",
                    "case_id": case_id,
                    "pattern_type": "CROSS_SOURCE_PRESENCE",
                    "severity": "medium",
                    "entities_involved": [name],
                    "evidence": list(srcs),
                    "timestamp": None,
                    "explanation": f"Entity '{name}' appears in sources: {', '.join(sorted(srcs))}.",
                }
            )

    # RULE 4: HIGH TRANSACTION VALUE
    amounts = [float(r.get("amount")) for _, r in case["datasets"]["transactions"].iterrows()]
    if len(amounts) >= 3:
        import statistics

        mu = statistics.mean(amounts)
        sd = statistics.stdev(amounts)
        threshold = mu + 2 * sd
    else:
        # fallback threshold
        threshold = 30000.0

    for _, row in case["datasets"]["transactions"].iterrows():
        amt = float(row.get("amount"))
        if amt > threshold:
            patterns.append(
                {
                    "pattern_id": f"HIGH_TXN::{case_id}::{row.get('transaction_id')}",
                    "case_id": case_id,
                    "pattern_type": "HIGH_TRANSACTION_VALUE",
                    "severity": "high" if amt > threshold * 1.5 else "medium",
                    "entities_involved": list(dict.fromkeys([row.get("sender"), row.get("receiver")])),
                    "evidence": {"transaction_id": row.get("transaction_id"), "amount": amt, "threshold": threshold},
                    "timestamp": _parse_ts(row.get("timestamp")).isoformat(),
                    "explanation": f"Transaction {row.get('transaction_id')} amount {amt} exceeds baseline {threshold:.2f}.",
                }
            )

    # RULE 5: HIGH CONNECTIVITY (degree significantly above median)
    degrees = [d for _, d in G.degree()]
    if degrees:
        import statistics

        med = statistics.median(degrees)
        sd = statistics.pstdev(degrees) if len(degrees) > 1 else 0.0
        for n, deg in G.degree():
            if sd > 0 and deg > med + 2 * sd:
                patterns.append(
                    {
                        "pattern_id": f"HIGH_CONN::{case_id}::{n}",
                        "case_id": case_id,
                        "pattern_type": "HIGH_CONNECTIVITY",
                        "severity": "medium" if deg <= med + 3 * sd else "high",
                        "entities_involved": [n],
                        "evidence": {"degree": deg, "median": med},
                        "timestamp": None,
                        "explanation": f"Entity {n} has degree {deg} which is above case median {med}.",
                    }
                )

    # ensure each pattern contains required fields and standardized keys
    for p in patterns:
        p.setdefault("timestamp", None)
        p.setdefault("explanation", "")

    return patterns
