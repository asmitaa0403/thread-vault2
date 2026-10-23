from collections import Counter
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.entity_resolution import process_case
from src.nlp import normalize_person

res = process_case('CG-2026-001')
print('Extracted counts:', Counter([e['entity_type'] for e in res['extracted_entities']]))
print('Total canonical:', res['counts']['total_canonical'])

vikas_occ = [e for e in res['extracted_entities'] if 'vikas' in (e.get('normalized_value') or '').lower() or 'vikas' in (e.get('raw_value') or '').lower()]
print('\nVikas occurrences (source,record_id,raw,normalized):')
for e in vikas_occ:
    print(e['source'], e['record_id'], e['raw_value'], '->', e['normalized_value'])

can = res['canonical_entities']
vikas_cids = []
for cid,ce in can.items():
    if ce.entity_type=='PERSON':
        names = set([n.lower() for n in ce.aliases])
        names.add((ce.canonical_name or '').lower())
        for n in list(names):
            if 'vikas' in n:
                vikas_cids.append((cid, ce.canonical_name, list(ce.aliases)[:10]))
                break
print('\nVikas canonical candidates:')
for item in vikas_cids:
    print(item)
