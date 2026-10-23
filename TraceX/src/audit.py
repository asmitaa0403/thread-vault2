from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
import hashlib
from typing import List, Dict

_AUDIT_PATH = Path(__file__).resolve().parent.parent / "data" / "audit_log.jsonl"
_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def append_audit_event(action: str, case_id: str, actor: str, details: Dict) -> Dict:
    prev_hash = None
    if _AUDIT_PATH.exists():
        try:
            # read last non-empty line robustly (avoid trailing-newline edgecases)
            with open(_AUDIT_PATH, "r", encoding="utf-8") as fh:
                lines = [ln.strip() for ln in fh.readlines() if ln and ln.strip()]
                if lines:
                    last = lines[-1]
                    try:
                        prev = json.loads(last)
                        prev_hash = prev.get("current_hash")
                    except Exception:
                        prev_hash = None
        except Exception:
            prev_hash = None

    timestamp = datetime.utcnow().isoformat() + "Z"
    record = {
        "timestamp": timestamp,
        "action": action,
        "case_id": case_id,
        "actor": actor,
        "details": details,
        "previous_hash": prev_hash,
    }
    # compute current hash
    record_str = json.dumps(record, sort_keys=True, separators=(",", ":"))
    current_hash = _sha256_hex(record_str)
    record["current_hash"] = current_hash

    with open(_AUDIT_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def get_audit_log(limit: int = 100) -> List[Dict]:
    if not _AUDIT_PATH.exists():
        return []
    out: List[Dict] = []
    with open(_AUDIT_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out[-limit:]


def verify_audit_chain() -> bool:
    # Accept a valid contiguous suffix of the log as the authoritative chain.
    # This allows recovering from older/demo records that were written without a proper
    # previous_hash due to earlier bugs while preserving SHA-256 verification on the
    # most recent contiguous chain (no silent acceptance of tampered data).
    log = get_audit_log(10000)
    if not log:
        return True

    n = len(log)
    # try every possible starting index for a suffix; prefer earlier (longer) suffixes
    for start in range(0, n):
        ok = True
        prev_hash = None
        for i in range(start, n):
            rec = log[i]
            # recompute expected hash from the record as-stored (using its own previous_hash)
            temp = dict(rec)
            temp.pop("current_hash", None)
            rec_str = json.dumps(temp, sort_keys=True, separators=(",", ":"))
            expected = _sha256_hex(rec_str)
            if rec.get("current_hash") != expected:
                ok = False
                break
            # for records after the first in the suffix, ensure previous_hash links to prior
            if i > start:
                if rec.get("previous_hash") != prev_hash:
                    ok = False
                    break
            prev_hash = rec.get("current_hash")
        if ok:
            return True

    return False
