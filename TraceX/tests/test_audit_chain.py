import tempfile
import json
from pathlib import Path

from src import audit


def test_audit_chain_valid_and_tamper():
    # use a temporary audit file to avoid touching real demo log
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.close()
    tmp_path = Path(tf.name)
    try:
        # point module to temp file
        orig = audit._AUDIT_PATH
        audit._AUDIT_PATH = tmp_path

        # append a few events
        a1 = audit.append_audit_event("test_event", "CG-2026-TEST", "Tester", {"note": "one"})
        a2 = audit.append_audit_event("test_event", "CG-2026-TEST", "Tester", {"note": "two"})
        a3 = audit.append_audit_event("test_event", "CG-2026-TEST", "Tester", {"note": "three"})

        # verification should succeed
        assert audit.verify_audit_chain() is True

        # tamper with the last record (should break verification)
        lines = tmp_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 3
        recs = [json.loads(l) for l in lines]
        # modify last record's details
        recs[-1]["details"]["note"] = "tampered"
        # rewrite file (do not recompute hashes to simulate tampering)
        tmp_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")

        # now verification should fail
        assert audit.verify_audit_chain() is False
    finally:
        # restore original path and cleanup
        audit._AUDIT_PATH = orig
        try:
            tmp_path.unlink()
        except Exception:
            pass
