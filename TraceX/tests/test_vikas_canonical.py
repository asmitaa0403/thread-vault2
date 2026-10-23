from src.entity_resolution import process_case


def test_vikas_canonical():
    res = process_case('CG-2026-001')
    can = res['canonical_entities']

    # find PERSON canonical entities that reference 'vikas'
    vikas_cids = []
    for cid, ce in can.items():
        if ce.entity_type != 'PERSON':
            continue
        names = set([a.lower() for a in ce.aliases])
        names.add((ce.canonical_name or '').lower())
        for n in names:
            if 'vikas' in n:
                vikas_cids.append((cid, ce))
                break

    assert len(vikas_cids) >= 1, "No PERSON canonical entities contain 'vikas'"
    cid, ce = vikas_cids[0]

    # canonical name should be the full name 'Vikas Patil'
    assert 'vikas patil' in (ce.canonical_name or '').lower(), f"Expected canonical name to contain 'Vikas Patil', got {ce.canonical_name}"

    # both variants preserved in aliases
    alias_texts = [a.lower() for a in ce.aliases]
    assert any('vikas patil' in a for a in alias_texts) or 'vikas patil' in (ce.canonical_name or '').lower()
    assert any(a == 'vikas' or ' vikas ' in f' {a} ' for a in alias_texts)
