from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime

from .ingestion import load_case
from .graph import build_case_graph
from .anomaly import detect_patterns


def explain_pattern(pattern: Dict[str, Any], case_id: str) -> Dict[str, Any]:
    p_type = pattern.get("pattern_type")
    expl = pattern.get("explanation", "")
    # Build human-readable WHY and include evidence
    # Provide the explanation text (do not prefix with 'WHY WAS THIS FLAGGED?')
    return {**pattern, "why": expl}


def explain_patterns(case_id: str) -> List[Dict[str, Any]]:
    patterns = detect_patterns(case_id)
    explained = [explain_pattern(p, case_id) for p in patterns]
    return explained


def get_investigation_timeline(case_id: str) -> List[Dict[str, Any]]:
    case = load_case(case_id)
    events: List[Dict[str, Any]] = []

    # FIR (date only)
    for _, row in case["datasets"]["fir"].iterrows():
        dt = row.get("date")
        events.append(
            {
                "timestamp": str(dt),
                "event_type": "FIR",
                "description": row.get("description"),
                "entities": [],
                "source": "fir",
                "record_id": row.get("fir_id"),
            }
        )

    # CDR
    for _, row in case["datasets"]["cdr"].iterrows():
        events.append(
            {
                "timestamp": row.get("timestamp"),
                "event_type": "CALL",
                "description": f"Call from {row.get('caller')} to {row.get('receiver')} ({row.get('duration_seconds')}s)",
                "entities": [row.get("caller"), row.get("receiver")],
                "source": "cdr",
                "record_id": row.get("cdr_id"),
            }
        )

    # Transactions
    for _, row in case["datasets"]["transactions"].iterrows():
        events.append(
            {
                "timestamp": row.get("timestamp"),
                "event_type": "TRANSACTION",
                "description": f"{row.get('sender')} paid {row.get('receiver')} amount {row.get('amount')}",
                "entities": [row.get("sender"), row.get("receiver")],
                "source": "transactions",
                "record_id": row.get("transaction_id"),
            }
        )

    # Social
    for _, row in case["datasets"]["social"].iterrows():
        events.append(
            {
                "timestamp": row.get("timestamp"),
                "event_type": "SOCIAL",
                "description": row.get("content"),
                "entities": [row.get("author"), row.get("mentioned_person")],
                "source": "social",
                "record_id": row.get("post_id"),
            }
        )

    # sort chronologically where possible
    def _to_key(e):
        ts = e.get("timestamp")
        try:
            return datetime.fromisoformat(str(ts))
        except Exception:
            try:
                return datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    return datetime.strptime(str(ts), "%Y-%m-%d")
                except Exception:
                    return datetime.max

    events.sort(key=_to_key)
    return events
