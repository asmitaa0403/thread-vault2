from src import nlp

print('spaCy loaded:', nlp.nlp is not None)
print('Normalize person:', nlp.normalize_person('Vikas  Patil'))
print('Phone norm:', nlp.normalize_phone('+91-98765 43210'))
print('Vehicle norm:', nlp.normalize_vehicle('MH 12 AB 1234'))
print('Account norm:', nlp.normalize_account(' acc-123_456 '))
print('Extract PERSON from text:', nlp.extract_entities_from_text('Call with Vikas Patil and Rohit Sharma at Andheri', 'test', 'r1', 'CG-2026-001'))
