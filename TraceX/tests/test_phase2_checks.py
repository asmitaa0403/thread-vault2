from src import nlp
from src.entity_resolution import process_case

case_id = 'CG-2026-001'
print('spaCy loaded:', nlp.nlp is not None)
print('normalize examples:')
print('  Vikas  Patil ->', nlp.normalize_person('Vikas  Patil'))
print('  vikas patil ->', nlp.normalize_person('vikas patil'))
print('  Vikas Patil ->', nlp.normalize_person('Vikas Patil'))

res = process_case(case_id)
extracted = res['extracted_entities']
canonical = res['canonical_entities']

# Find PERSON extracted with normalized == vikas patil
target_norm = nlp.normalize_person('Vikas Patil')
persons = [e for e in extracted if e['entity_type']=='PERSON' and e['normalized_value']==target_norm]
print('Extracted PERSON entries matching normalized "vikas patil":', len(persons))
for p in persons[:10]:
    print(' ', p)

# Find canonical entity that includes variants
matched_cids = []
variants = {'vikas patil','Vikas Patil','Vikas  Patil'}
for cid, ce in canonical.items():
    aliases_lower = {a.lower() for a in ce.aliases}
    if any(v.lower() in aliases_lower or v.lower() in ce.canonical_name.lower() for v in variants):
        matched_cids.append(cid)

print('Canonical IDs matching Vikas variants:', matched_cids)
if matched_cids:
    cid = matched_cids[0]
    ce = canonical[cid]
    print('Canonical entity:', cid, ce.entity_type, ce.canonical_name)
    print('Aliases:', ce.aliases)
    print('Source records count:', len(ce.source_records))
    print('Case IDs:', ce.case_ids)
else:
    print('No canonical entity found for Vikas variants')
